from database.client import ClientDb


def add_client(name: str, email: str, phone_number: str) -> None:
    """Add a client to the database"""
    ClientDb.add_client(name, email, phone_number)


def add_item(name: str, item_code: str) -> None:
    """Add an item to the database"""
    ClientDb.add_item(name, item_code)
