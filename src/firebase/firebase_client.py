import typing as T

import firebase_admin

from firebase_admin import firestore
from firebase_admin import credentials

from database.models.client import ClientSchema


class FirebaseClient:
    def __init__(self, credentials_file: str) -> None:
        if not firebase_admin._apps:
            auth = credentials.Certificate(credentials_file)
            firebase_admin.initialize_app(auth)
        self.db = firestore.client()

        self.clients_ref = self.db.collection("clients")

    def _get_client_document(self, client: ClientSchema) -> T.Optional[T.Any]:
        db_setup = {}
        for doc in self.clients_ref.stream():
            db_setup[doc.id] = doc.to_dict()

        email = client["email"]

        for db_email, db_config in db_setup.items():
            try:
                notification_email = db_config["preferences"]["notifications"]["email"][
                    "email"
                ].lower()
            except:
                continue

            if notification_email == email:
                email = db_email.lower()
                return self.clients_ref.document(email)

        return None

    def run(self) -> None:
        pass
