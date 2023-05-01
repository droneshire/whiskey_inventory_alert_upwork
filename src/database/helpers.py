from database.client import ClientDb


def add_client(name: str, email: str, phone_number: str) -> None:
    """Add a client to the database"""
    ClientDb.add_client(name, email, phone_number)


def add_item(name: str, item_code: str) -> None:
    """Add an item to the database"""
    ClientDb.add_item(name, item_code)


def track_item(name: str, item_code: str, do_track: bool) -> None:
    """Modify tracking status of item in the database"""
    with ClientDb(name).item(item_code) as item:
        if item is not None:
            item.is_tracking = do_track
            return

    add_item(name, item_code)
