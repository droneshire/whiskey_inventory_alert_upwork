import os
import time
import typing as T
from contextlib import contextmanager

import dotenv
from sqlalchemy.sql import func

from database.connect import ManagedSession
from database.models.client import Client
from database.models.item import Item
from util import log

DEFAULT_DB = os.environ.get("DEFAULT_DB", "")


class ClientDb:
    def __init__(self, name: str, db_str: str = DEFAULT_DB) -> None:
        self.id = name
        self.items: T.List[Item] = []
        self.db_str = db_str

        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                log.print_fail(f"Client {name} not in db!")
                return
            for item in client.items:
                self.items.append(item)

    @contextmanager
    def client(self) -> T.Iterator[Client]:
        with ManagedSession() as db:
            name = db.query(Client).filter(Client.id == self.id).first()

            yield name

            if name is None:
                return

            name.last_updated = func.now()

            db.add(name)

    @contextmanager
    def item(self, nc_code: str) -> T.Iterator[Item]:
        with ManagedSession() as db:
            item = db.query(Item).filter(Item.nc_code == nc_code).first()

            yield item

            if item is None:
                return

            db.add(item)

    @staticmethod
    def get_client_names() -> T.List[str]:
        clients = []
        with ManagedSession() as db:
            clients_db = db.query(Client).all()
            clients = [c.id for c in clients_db]
        return clients

    @staticmethod
    def delete_client(name: str, db_str: str = DEFAULT_DB, verbose: bool = False) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                if verbose:
                    log.print_warn(f"Not deleting {name}, it's not in db")
                return

            db.query(Item).filter(Item.client_id == client.id).delete()
            db.query(Client).filter(Client.id == name).delete()

    @staticmethod
    def add_client(
        name: str,
        email: str = "",
        phone_number: str = "",
        db_str: str = DEFAULT_DB,
        verbose: bool = False,
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is not None:
                if verbose:
                    log.print_warn(f"Skipping {name} add, already in db")
                return

            log.print_ok_arrow(f"Created {name} client")

            client = Client(
                id=name, email=email, phone_number=phone_number, last_updated=func.now()
            )

            db.add(client)

    @staticmethod
    def delete_item(
        name: str, nc_code: str, db_str: str = DEFAULT_DB, verbose: bool = False
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                if verbose:
                    log.print_warn(f"Not deleting {nc_code}, {name} doesn't exist!")
                return

            item = db.query(Item).filter(Item.nc_code == nc_code).first()
            if item is None:
                if verbose:
                    log.print_warn(f"Not deleting {nc_code}, it's not in client!")
                return

            db.query(Item).filter(Item.client_id == name).filter(Item.nc_code == nc_code).delete()

    @staticmethod
    def add_item(
        name: str,
        nc_code: str,
        brand_name: str = None,
        total_available: int = None,
        size: str = None,
        cases_per_pallet: int = None,
        supplier: str = None,
        supplier_allotment: int = None,
        broker_name: str = None,
        is_tracking: bool = True,
        db_str: str = DEFAULT_DB,
        verbose: bool = False,
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                log.print_fail(f"Failed to add item, user doesn't exist!")
                return

            if nc_code in [i.nc_code for i in client.items]:
                if verbose:
                    log.print_warn(f"Skipping add {nc_code}, already in client!")
                return

            log.print_ok_arrow(f"Created item [{nc_code}] for {client.id}")

            item = Item(
                client_id=client.id,
                nc_code=nc_code,
            )

            if brand_name is not None:
                item.brand_name = brand_name
            if total_available is not None:
                item.total_available = total_available
            if size is not None:
                item.size = size
            if cases_per_pallet is not None:
                item.cases_per_pallet = cases_per_pallet
            if supplier is not None:
                item.supplier = supplier
            if supplier_allotment is not None:
                item.supplier_allotment = supplier_allotment
            if broker_name is not None:
                item.broker_name = broker_name

            item.is_tracking = is_tracking
            db.add(item)
