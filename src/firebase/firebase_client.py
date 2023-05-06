import copy
import datetime
import enum
import json
import threading
import typing as T

import deepdiff
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.watch import DocumentChange, Watch
from sqlalchemy.sql import func

from database.client import ClientDb
from database.helpers import add_client, add_item, track_item
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

    def __init__(self, credentials_file: str, verbose: bool = False) -> None:
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()
        self.verbose = verbose

        self.clients_ref = self.db.collection("clients")

        self.clients_watcher = self.clients_ref.on_snapshot(self._collection_snapshot_handler)

        self.db_cache: defs.Client = {}

        self.callback_done = threading.Event()
        self.db_cache_lock = threading.Lock()

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

        client_dict = copy.deepcopy(self.db_cache[client])

        if client_dict.get("preferences", {}).get("notifications", {}).get("alertTimeRange"):
            del client_dict["preferences"]["notifications"]["alertTimeRange"]

            client_dict_firestore = json.loads(json.dumps(client_dict))

            client_dict_firestore["preferences"]["notifications"]["alertTimeRange"] = [
                datetime.datetime.strptime(t, self.TIME_FORMAT)
                for t in self.db_cache[client]["preferences"]["notifications"]["alertTimeRange"]
            ]
        else:
            client_dict_firestore = json.loads(json.dumps(client_dict))

        self.clients_ref.document(client).set(client_dict_firestore)

    def _collection_snapshot_handler(
        self,
        collection_snapshot: T.List[DocumentSnapshot],
        changed_docs: T.List[DocumentChange],
        read_time: T.Any,
    ) -> None:
        log.print_warn(f"Received collection snapshot for {len(collection_snapshot)} documents")

        clients = self.db_cache.keys()
        with self.db_cache_lock:
            self.db_cache = {}
            for doc in collection_snapshot:
                if self.verbose:
                    log.print_ok_blue(
                        f"Document data: {json.dumps(doc.to_dict(), indent=4, sort_keys=True)}"
                    )

                db_time: DatetimeWithNanoseconds
                db_times = []

                doc_dict = doc.to_dict()

                if doc_dict:
                    for db_time in doc_dict["preferences"]["notifications"]["alertTimeRange"]:
                        db_times.append(db_time.strftime(self.TIME_FORMAT))
                    doc_dict["preferences"]["notifications"]["alertTimeRange"] = db_times

                    self.db_cache[doc.id] = doc_dict

        for client in clients:
            if client not in self.db_cache:
                self._delete_client(client)

        for change in changed_docs:
            doc_id = change.document.id
            if change.type.name == Changes.ADDED.name:
                log.print_ok_blue(f"Added document: {doc_id}")
                email = safe_get(
                    self.db_cache[doc_id], "preferences.notifications.email.email".split("."), ""
                )
                phone_number = safe_get(
                    self.db_cache[doc_id],
                    "preferences.notifications.sms.phoneNumber".split("."),
                    "",
                )
                if phone_number and not phone_number.startswith("+1"):
                    phone_number = "+1" + phone_number
                add_client(doc_id, email, phone_number)
            elif change.type.name == Changes.MODIFIED.name:
                log.print_ok_blue(f"Modified document: {doc_id}")
                add_client(doc_id, email, phone_number)
            elif change.type.name == Changes.REMOVED.name:
                log.print_ok_blue(f"Removed document: {doc_id}")
                self._delete_client(doc_id)
                continue

        self.callback_done.set()

    def _handle_firebase_update(self, client: str, db_client: defs.Client) -> None:
        log.print_normal(f"Checking to see if we need to update {client} in database...")
        old_db_client = copy.deepcopy(db_client)

        if not db_client:
            db_client = copy.deepcopy(defs.NULL_CLIENT)
            log.print_normal(
                f"Initializing new client {client} in database:\n{json.dumps(db_client, indent=4, sort_keys=True)}"
            )
        elif check_dict_keys_recursive(defs.NULL_CLIENT, db_client):
            patch_missing_keys_recursive(defs.NULL_CLIENT, db_client)

        email = safe_get(
            self.db_cache[client], "preferences.notifications.email.email".split("."), ""
        )
        phone_number = safe_get(
            self.db_cache[client], "preferences.notifications.sms.phoneNumber".split("."), ""
        )
        if phone_number and not phone_number.startswith("+1"):
            phone_number = "+1" + phone_number

        for nc_code, info in safe_get(db_client, "inventory.items".split(".")).items():
            if info.get("action", "") == defs.Actions.TRACKING.value:
                add_item(client, nc_code)
            elif info.get("action", "") == defs.Actions.NOT_TRACKING.value:
                track_item(client, nc_code, False)

            with ClientDb(client).item(nc_code) as item:
                if item and item.nc_code == nc_code and item.brand_name:
                    db_client["inventory"]["items"][nc_code]["name"] = item.brand_name
                    db_client["inventory"]["items"][nc_code]["available"] = item.total_available

        with ClientDb(client).client() as db:
            if db is not None:
                db.email = email
                db.phone_number = phone_number
                db.threshold_inventory = safe_get(
                    db_client, "inventory.inventoryChange".split("."), 0
                )
                db.phone_alerts = safe_get(
                    db_client, "preferences.notifications.sms.updatesEnabled".split("."), False
                )
                db.email_alerts = safe_get(
                    db_client, "preferences.notifications.email.updatesEnabled".split("."), False
                )
                db.alert_time_zone = safe_get(
                    db_client, "preferences.notifications.alertTimeZone.value".split("."), ""
                )
                alert_range: T.List[datetime.datetime] = safe_get(
                    db_client, "preferences.notifications.alertTimeRange".split("."), []
                )
                if len(alert_range) == 2:
                    db.alert_time_range_start = datetime.datetime.strptime(
                        alert_range[0], self.TIME_FORMAT
                    )
                    db.alert_time_range_end = datetime.datetime.strptime(
                        alert_range[1], self.TIME_FORMAT
                    )

                items = [i.nc_code for i in db.items]

        items_to_delete = []
        for nc_code in items:
            with ClientDb(client).item(nc_code) as db_item:
                if db_item is not None and nc_code not in db_client["inventory"]["items"]:
                    log.print_warn(f"Deleting item {nc_code} from client {client} in database")
                    items_to_delete.append(nc_code)

        # Delete items that are no longer being tracked outside of the previous
        # db session context
        for nc_code in items_to_delete:
            ClientDb.delete_item(client, nc_code)

        self._maybe_upload_db_cache_to_firestore(client, old_db_client, db_client)

    def update_from_firebase(self) -> None:
        """
        Synchronous update from firebase database. We do this periodically to ensure
        that we are not missing any updates from the database. This is a fallback
        mechanism in case the watcher fails, which it seems to periodically do.
        """
        log.print_warn(f"Updating from firebase database instead of cache")
        clients = self.db_cache.keys()
        with self.db_cache_lock:
            self.db_cache = {}
            for doc in self.clients_ref.list_documents():
                doc_dict = doc.get().to_dict()
                try:
                    db_time: DatetimeWithNanoseconds
                    db_times = []
                    for db_time in doc_dict["preferences"]["notifications"]["alertTimeRange"]:
                        db_times.append(db_time.strftime("%Y_%m_%d%H_%M_%S_%f"))
                    doc_dict["preferences"]["notifications"]["alertTimeRange"] = db_times
                except KeyError:
                    log.format_fail("Failed to convert DateTimeWithNanoseconds to datetime")
                self.db_cache[doc.id] = doc_dict

        for client in clients:
            if client not in self.db_cache:
                self._delete_client(client)

    def check_and_maybe_update_to_firebase(self, client: str, item_code: str) -> None:
        items = safe_get(self.db_cache, f"{client}.inventoryitems".split("."))
        if not items:
            return

        db_client = copy.deepcopy(self.db_cache[client])

        for nc_code, info in db_client["inventory"]["items"].items():
            with ClientDb(client).item(nc_code) as item:
                if item and item.nc_code == nc_code and item.brand_name and item.total_available:
                    db_client["inventory"]["items"][nc_code]["name"] = item.brand_name
                    db_client["inventory"]["items"][nc_code]["available"] = item.total_available

        self._maybe_upload_db_cache_to_firestore(client, self.db_cache[client], db_client)

    def check_and_maybe_handle_firebase_db_updates(self) -> None:
        if self.callback_done.is_set():
            self.callback_done.clear()
            log.print_bright("Handling firebase database updates")
            for client, info in self.db_cache.items():
                self._handle_firebase_update(client, info)
