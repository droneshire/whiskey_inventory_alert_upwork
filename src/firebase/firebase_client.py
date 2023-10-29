import copy
import datetime
import enum
import json
import threading
import time
import typing as T

import deepdiff
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.watch import DocumentChange
from sqlalchemy.sql import func

from database.client import ClientDb
from database.models.client import ClientSchema
from database.models.item import Item
from firebase import defs
from util import log
from util.dict_util import check_dict_keys_recursive, patch_missing_keys_recursive, safe_get


class Changes(enum.Enum):
    ADDED = 1
    MODIFIED = 2
    REMOVED = 3


class FirebaseClient:
    TIME_FORMAT = "%Y_%m_%d%H_%M_%S_%f"
    HEALTH_PING_TIME = 60 * 30

    def __init__(self, credentials_file: str, verbose: bool = False) -> None:
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()
        self.verbose = verbose

        self.clients_ref: CollectionReference = self.db.collection("clients")
        self.admin_ref: CollectionReference = self.db.collection("admin")

        self.clients_watcher = self.clients_ref.on_snapshot(self._collection_snapshot_handler)

        self.db_cache: defs.Client = {}

        self.callback_done = threading.Event()
        self.db_cache_lock = threading.Lock()

        self.last_health_ping = None

    def _delete_client(self, name: str) -> None:
        ClientDb.delete_client(name)
        with self.db_cache_lock:
            if name in self.db_cache:
                del self.db_cache[name]
        log.print_warn(f"Deleting client {name} from database")

    def _maybe_upload_db_cache_to_firestore(
        self, client: str, old_db_client: defs.Client, db_client: defs.Client
    ) -> None:
        diff = deepdiff.DeepDiff(
            old_db_client,
            db_client,
            ignore_order=True,
        )
        if not diff:
            return

        log.print_normal(
            f"Updated client {client} in database:\n{diff.to_json(indent=4, sort_keys=True)}"
        )

        client_dict_firestore = json.loads(json.dumps(db_client))

        self.clients_ref.document(client).set(client_dict_firestore)

    def _collection_snapshot_handler(
        self,
        collection_snapshot: T.List[DocumentSnapshot],
        changed_docs: T.List[DocumentChange],
        read_time: T.Any,
    ) -> None:
        log.print_warn(f"Received collection snapshot for {len(collection_snapshot)} documents")

        with self.db_cache_lock:
            self.db_cache = {}
            for doc in collection_snapshot:
                self.db_cache[doc.id] = doc.to_dict()

        for client in self.db_cache.keys():
            if client not in self.db_cache:
                self._delete_client(client)

        for change in changed_docs:
            doc_id = change.document.id
            email = safe_get(
                self.db_cache[doc_id], "preferences.notifications.email.email".split("."), ""
            )
            phone_numbers_dict = safe_get(
                self.db_cache[doc_id],
                "preferences.notifications.sms.phoneNumbers".split("."),
                {},
            )
            # legacy database value
            phone_number_val = safe_get(
                self.db_cache[client], "preferences.notifications.sms.phoneNumber".split("."), ""
            )

            phone_numbers = list(phone_numbers_dict.values())
            if not phone_numbers and phone_number_val:
                phone_numbers = [phone_number_val]

            for index, phone_number in enumerate(phone_numbers):
                # remove any leading us country code and any parenthesis or brackets from phone num
                phone_number = "".join([c for c in phone_number if c.isdigit()])
                if phone_number.startswith("1") and len(phone_number) == 11:
                    phone_number = phone_number[1:]

            if change.type == Changes.ADDED:
                log.print_ok_blue(f"Added document: {doc_id}")

                ClientDb.add_client(doc_id, email, phone_numbers)
            elif change.type == Changes.MODIFIED:
                log.print_ok_blue(f"Modified document: {doc_id}")
                ClientDb.add_client(doc_id, email, phone_numbers)
            elif change.type == Changes.REMOVED:
                log.print_ok_blue(f"Removed document: {doc_id}")
                self._delete_client(doc_id)
                continue

        self.callback_done.set()

    def _handle_firebase_update(self, client: str, db_client: defs.Client) -> None:
        log.print_normal(f"Checking to see if we need to update {client} databases...")
        old_db_client = copy.deepcopy(db_client)

        if not db_client:
            db_client = copy.deepcopy(defs.NULL_CLIENT)
            log.print_normal(
                f"Initializing new client {client} in database:\n{json.dumps(db_client, indent=4, sort_keys=True)}"
            )
        missing_keys = check_dict_keys_recursive(defs.NULL_CLIENT, db_client)
        if missing_keys:
            log.print_warn(f"Missing keys in client {client}:\n{missing_keys}")
            patch_missing_keys_recursive(defs.NULL_CLIENT, db_client)

        email = safe_get(old_db_client, "preferences.notifications.email.email".split("."), "")

        # legacy database value
        phone_number_val = safe_get(
            old_db_client, "preferences.notifications.sms.phoneNumber".split("."), ""
        )
        phone_numbers_dict = safe_get(
            old_db_client, "preferences.notifications.sms.phoneNumbers".split("."), {}
        )

        phone_numbers = list(phone_numbers_dict.values())
        if not phone_numbers and phone_number_val:
            phone_numbers_to_parse = [phone_number_val]

        for index, phone_number in enumerate(phone_numbers):
            # remove any leading us country code and any parenthesis or brackets from phone num
            phone_number = "".join([c for c in phone_number if c.isdigit()])

            db_client["preferences"]["notifications"]["sms"]["phoneNumbers"][
                str(index)
            ] = phone_number

            if phone_number.startswith("1") and len(phone_number) == 11:
                phone_number = phone_number[1:]
            if phone_number and not phone_number.startswith("+1"):
                phone_number = "+1" + phone_number
            phone_numbers.append(phone_number)

        with ClientDb.client(client) as db:
            if not db:
                self._maybe_upload_db_cache_to_firestore(client, old_db_client, db_client)
                return

            client_schema = ClientSchema().dump(db)

        items_schema = ClientDb.all_items()
        client_items_list = [i["id"] for i in client_schema["items"]]
        client_tracking_list = [t["nc_code"] for t in client_schema["tracked_items"]]

        for nc_code, info in safe_get(db_client, "inventory.items".split(".")).items():
            is_tracking_in_firebase = info.get("action", "") == defs.Actions.TRACKING.value
            if nc_code in client_items_list:
                is_tracking_in_db = nc_code in client_tracking_list
                if is_tracking_in_db != is_tracking_in_firebase:
                    log.print_normal(
                        f"Updating tracking status for {nc_code} in database: {is_tracking_in_firebase}"
                    )
                    ClientDb.add_track_item(client, nc_code, is_tracking_in_firebase)
            else:
                ClientDb.add_item_to_client(client, nc_code)
                ClientDb.add_track_item(client, nc_code, is_tracking_in_firebase)

            if nc_code not in items_schema:
                ClientDb.add_or_update_item(nc_code)
            else:
                db_client["inventory"]["items"][nc_code]["name"] = items_schema[nc_code][
                    "brand_name"
                ]
                db_client["inventory"]["items"][nc_code]["available"] = items_schema[nc_code][
                    "total_available"
                ]

        with ClientDb.client(client) as db:
            db.email = email
            db.update_on_new_data = safe_get(
                db_client, "preferences.updateOnNewData".split("."), False
            )
            db.threshold_inventory = safe_get(db_client, "inventory.inventoryChange".split("."), 0)
            db.min_hours_since_out_of_stock = safe_get(
                db_client, "inventory.min_hours_since_out_of_stock".split("."), 0
            )
            db.phone_alerts = safe_get(
                db_client, "preferences.notifications.sms.updatesEnabled".split("."), False
            )
            db.email_alerts = safe_get(
                db_client, "preferences.notifications.email.updatesEnabled".split("."), False
            )
            db.alert_time_zone = safe_get(
                db_client, "preferences.notifications.sms.alertTimeZone.value".split("."), ""
            )
            db.alert_range_enabled: T.List[datetime.datetime] = safe_get(
                db_client, "preferences.notifications.sms.alertWindowEnabled".split("."), False
            )
            alert_range: T.List[datetime.datetime] = safe_get(
                db_client, "preferences.notifications.sms.alertTimeRange".split("."), []
            )
            db.has_paid = safe_get(db_client, "accounting.hasPaid".split("."), False)
            db.next_billing_amount = safe_get(
                db_client, "accounting.nextBillingAmount".split("."), 0.0
            )
            if len(alert_range) == 2:
                db.alert_time_range_start = alert_range[0]
                db.alert_time_range_end = alert_range[1]

            nc_codes = [i.id for i in db.items]

            tracked_nc_codes = [i.nc_code for i in db.tracked_items]

        ClientDb.add_phone_numbers(client, phone_numbers)

        for nc_code in nc_codes:
            if nc_code not in db_client["inventory"]["items"]:
                log.print_warn(f"Deleting {nc_code} from client {client} in database")
                ClientDb.delete_item_association(client, nc_code)

        for nc_code in tracked_nc_codes:
            if nc_code not in db_client["inventory"]["items"]:
                log.print_warn(f"Deleting tracking {nc_code} from client {client} in database")
                ClientDb.delete_track_item(client, nc_code)

        self._maybe_upload_db_cache_to_firestore(client, old_db_client, db_client)

    def update_watchers(self) -> None:
        log.print_warn(f"Updating watcher...")
        if self.clients_watcher:
            self.clients_watcher.unsubscribe()

        self.clients_watcher = self.clients_ref.on_snapshot(self._collection_snapshot_handler)

    def update_from_firebase(self) -> None:
        """
        Synchronous update from firebase database. We do this periodically to ensure
        that we are not missing any updates from the database. This is a fallback
        mechanism in case the watcher fails, which it seems to periodically do.
        """
        log.print_warn(f"Updating from firebase database instead of cache")
        with self.db_cache_lock:
            self.db_cache = {}
            for doc in self.clients_ref.list_documents():
                self.db_cache[doc.id] = doc.get().to_dict()

        for client in self.db_cache.keys():
            if client not in self.db_cache:
                self._delete_client(client)

        self.callback_done.set()

    def check_and_maybe_update_to_firebase(self, client: str, item_code: str) -> None:
        items = safe_get(self.db_cache, f"{client}.inventoryitems".split("."))
        if not items:
            return

        db_client = copy.deepcopy(self.db_cache[client])

        for nc_code, info in db_client["inventory"]["items"].items():
            with ClientDb.item(nc_code) as item:
                if item and item.id == nc_code and item.brand_name and item.total_available:
                    db_client["inventory"]["items"][nc_code]["name"] = item.brand_name
                    db_client["inventory"]["items"][nc_code]["available"] = item.total_available

        self._maybe_upload_db_cache_to_firestore(client, self.db_cache[client], db_client)

    def check_and_maybe_handle_firebase_db_updates(self) -> None:
        if self.callback_done.is_set():
            self.callback_done.clear()
            log.print_bright("Handling firebase database updates")
            for client, info in self.db_cache.items():
                self._handle_firebase_update(client, info)

    def health_ping(self) -> None:
        if self.last_health_ping and time.time() - self.last_health_ping < self.HEALTH_PING_TIME:
            return

        self.last_health_ping = time.time()

        log.print_ok_arrow("Health ping")
        self.admin_ref.document("health_monitor").set(
            {"heartbeat": firestore.SERVER_TIMESTAMP}, merge=["heartbeat"]
        )

    def add_items_to_firebase(self, client: str, items_dict: defs.Client) -> None:
        log.print_warn(f"Adding items to firebase")
        doc_ref: DocumentReference = self.clients_ref.document(client)
        items_dict = doc_ref.get(["inventory.items"]).to_dict()
        log.print_bold(f"Items before: {len(items_dict['inventory']['items'].keys())}")
        doc_ref.set(items_dict, merge=["inventory.items"])
        items_dict = doc_ref.get(["inventory.items"]).to_dict()
        log.print_bold(f"Items after: {len(items_dict['inventory']['items'].keys())}")
