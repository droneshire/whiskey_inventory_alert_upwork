import copy
import enum
import json
import typing as T

import deepdiff
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.collection import CollectionReference
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.watch import DocumentChange, Watch
from sqlalchemy.sql import func

from database.client import ClientDb
from database.helpers import add_client, add_item
from database.models.client import ClientSchema
from database.models.item import Item
from firebase import types
from util import log


class FirebaseClient:
    def __init__(self, credentials_file: str) -> None:
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()

        self.clients_ref = self.db.collection("clients")

        self.clients_watcher = self.clients_ref.on_snapshot(self._collection_snapshot_handler)
        self.client_watcher: T.Dict[str, Watch] = {}

        collection_user_doc: DocumentReference
        for collection_user_doc in self.clients_ref.list_documents():
            self.client_watcher[collection_user_doc.id] = collection_user_doc.on_snapshot(
                self._document_snapshot_handler
            )

        self.db_cache = {}

    def _collection_snapshot_handler(
        self,
        collection_snapshot: DocumentSnapshot,
        changed_docs: T.List[DocumentChange],
        read_time: T.Any,
    ) -> None:
        log.print_warn("\nReceived collection snapshots")
        for change in changed_docs:
            doc: DocumentSnapshot = change.document
            db_dict: types.Client = doc.to_dict()

            log.print_ok_blue(f"Received collection snapshot: {doc.id}")
            log.print_ok_blue(f"Collection data: {json.dumps(db_dict, indent=4, sort_keys=True)}")

            if not db_dict:
                new_db_dict = copy.deepcopy(types.NULL_CLIENT)
                log.print_normal(
                    f"Initializing new client {doc.id} in database:\n{json.dumps(new_db_dict, indent=4, sort_keys=True)}"
                )
                self.clients_ref.document(doc.id).set(json.loads(json.dumps(new_db_dict)))
            self.db_cache[doc.id] = copy.deepcopy(db_dict)

    def _document_snapshot_handler(
        self,
        document_snapshots: T.List[DocumentSnapshot],
        changes: DocumentChange,
        read_time: T.Any,
    ) -> None:
        doc = document_snapshots[0]
        db_dict = doc.to_dict()
        old_db_dict = copy.deepcopy(db_dict)

        log.print_warn(f"\nReceived document snapshot: {doc.id}")
        log.print_ok_blue(f"Document data: {json.dumps(doc.to_dict(), indent=4, sort_keys=True)}")

        try:
            email = db_dict["preferences"]["notifications"]["email"]["email"]
            if not email:
                log.print_fail(f"Client {doc.id} is not activated!")
                return
        except KeyError:
            log.print_fail(f"Client {doc.id} is not activated!")
            return

        phone_number = db_dict["preferences"]["notifications"]["sms"]["phoneNumber"]
        if not phone_number.startswith("+1"):
            phone_number = "+1" + phone_number

        add_client(doc.id, email, phone_number)

        for nc_code, info in db_dict["inventory"]["items"].items():
            if info["action"] == types.Actions.TRACKING.value:
                add_item(doc.id, nc_code)
            elif info["action"] == types.Actions.NOT_TRACKING.value:
                track_item(doc.id, nc_code, False)

            with ClientDb(doc.id).item(nc_code) as item:
                if item.nc_code == nc_code and item.brand_name:
                    db_dict["inventory"]["items"][nc_code]["name"] = item.brand_name
                    db_dict["inventory"]["items"][nc_code]["available"] = item.total_available

        with ClientDb(doc.id).client() as client:
            client.email = email
            client.phone_number = phone_number
            client.threshold_inventory = db_dict["inventory"]["inventoryChange"]
            client.phone_alerts = db_dict["preferences"]["notifications"]["sms"]["updatesEnabled"]
            client.email_alerts = db_dict["preferences"]["notifications"]["email"]["updatesEnabled"]

        self.db_cache[doc.id] = copy.deepcopy(db_dict)

        diff = deepdiff.DeepDiff(
            old_db_dict,
            db_dict,
            ignore_order=True,
            ignore_numeric_type_changes=True,
            ignore_order_func=True,
        )
        if diff:
            log.print_normal(
                f"Updated client {doc.id} in database:\n{json.dumps(db_dict, indent=4, sort_keys=True)}"
            )
            self.clients_ref.document(doc.id).set(json.loads(json.dumps(db_dict)))
        else:
            log.print_warn(f"Client {doc.id} already up to date in database!")

    def check_and_maybe_update_items(self, client: str, item_code: str) -> None:
        items = self.db_cache.get(client, {}).get("inventory", {}).get("items", [])
        if not items:
            return

        update_needed = False
        if (
            item_code not in items
            or items[item_code]["available"] == -1
            or items[item_code]["name"] == ""
        ):
            update_needed = True

        if not update_needed:
            return

        db_dict = copy.deepcopy(self.db_cache[client])

        for nc_code, info in db_dict["inventory"]["items"].items():
            with ClientDb(client).item(nc_code) as item:
                if item.nc_code == nc_code and item.brand_name and item.total_available:
                    db_dict["inventory"]["items"][nc_code]["name"] = item.brand_name
                    db_dict["inventory"]["items"][nc_code]["available"] = item.total_available

        diff = deepdiff.DeepDiff(
            self.db_cache[client],
            db_dict,
            ignore_order=True,
            ignore_numeric_type_changes=True,
            ignore_order_func=True,
        )
        if diff:
            log.print_normal(
                f"Updated client {client} in database:\n{json.dumps(db_dict, indent=4, sort_keys=True)}"
            )
            self.clients_ref.document(client).set(json.loads(json.dumps(db_dict)))
        else:
            log.print_warn(f"Client {client} already up to date in database!")
