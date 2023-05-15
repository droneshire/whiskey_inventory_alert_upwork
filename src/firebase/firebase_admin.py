import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.collection import CollectionReference


def set_reset(credentials_file: str, reset: bool = False) -> None:
    if not firebase_admin._apps:
        auth = credentials.Certificate(credentials_file)
        firebase_admin.initialize_app(auth)
    db = firestore.client()

    admin_ref: CollectionReference = db.collection("admin")
    admin_ref.document("health_monitor").set({"reset": reset}, merge=["reset"])


def get_reset(credentials_file: str) -> bool:
    if not firebase_admin._apps:
        auth = credentials.Certificate(credentials_file)
        firebase_admin.initialize_app(auth)
    db = firestore.client()

    admin_ref: CollectionReference = db.collection("admin")
    doc = admin_ref.document("health_monitor").get()
    return doc.to_dict().get("reset", False)
