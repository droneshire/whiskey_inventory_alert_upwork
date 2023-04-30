import enum
import json
import typing as T

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
from util import log


class Actions(enum.Enum):
    TRACKING = "TRACKING"
    NOT_TRACKING = "UNTRACKED"


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

    def _collection_snapshot_handler(
        self,
        collection_snapshot: DocumentSnapshot,
        changed_docs: T.List[DocumentChange],
        read_time: T.Any,
    ) -> None:
        log.print_warn("\nReceived collection snapshots")
        for change in changed_docs:
            doc: DocumentSnapshot = change.document
            db_dict = doc.to_dict()

            log.print_ok_blue(f"Received collection snapshot: {doc.id}")
            log.print_ok_blue(f"Collection data: {json.dumps(db_dict, indent=4, sort_keys=True)}")

    def _document_snapshot_handler(
        self,
        document_snapshots: T.List[DocumentSnapshot],
        changes: DocumentChange,
        read_time: T.Any,
    ) -> None:
        doc = document_snapshots[0]
        db_dict = doc.to_dict()

        log.print_warn(f"\nReceived document snapshot: {doc.id}")
        log.print_ok_blue(f"Document data: {json.dumps(doc.to_dict(), indent=4, sort_keys=True)}")

        email = db_dict["preferences"]["notifications"]["email"]["email"]

        phone_number = db_dict["preferences"]["notifications"]["sms"]["phoneNumber"]
        if not phone_number.startswith("+1"):
            phone_number = "+1" + phone_number

        add_client(doc.id, email, phone_number)

        db = ClientDb(name)

        for nc_code, action in db_dict["inventory"]["items"].items():
            if action["action"] == Actions.TRACKING.value:
                add_item(doc.id, nc_code)
            elif action["action"] == Actions.NOT_TRACKING.value:
                track_item(doc.id, nc_code, False)
            with db.client() as client:
                item: Item
                for item in client.items:
                    if item.nc_code != nc_code:
                        continue
                    db_dict["inventory"]["items"][nc_code]["name"] = item.brand_name
                    break

        with db.client() as client:
            client.email = email
            client.phone_number = phone_number
            client.last_updated = func.now()
            client.threshold_inventory = db_dict["inventory"]["inventoryChange"]
            client.phone_alerts = db_dict["preferences"]["notifications"]["sms"]["updatesEnabled"]
            client.email_alerts = db_dict["preferences"]["notifications"]["email"]["updatesEnabled"]

        log.print_normal(
            f"Updated client {doc.id} in database:\n{json.dumps(db_dict, indent=4, sort_keys=True)}"
        )
        doc.set(json.loads(json.dumps(db_dict)))

    def run(self) -> None:
        pass
