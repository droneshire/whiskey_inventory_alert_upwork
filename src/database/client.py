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

DEFAULT_DB = os.environ.get("DEFAULT_DB")


class ClientDb:
    def __init__(self, name: str, db_str: str = DEFAULT_DB) -> None:
        self.name = name
        self.items: T.List[Item] = []
        self.db_str = db_str

        with ManagedSession() as db:
            client = db.query(Client).filter(Client.name == name).first()
            assert client is not None, f"Client {self.name} not in DB!"
            for item in client.items:
                self.items.append(item)

    @contextmanager
    def client(self) -> T.Iterator[Client]:
        with ManagedSession() as db:
            name = db.query(Client).filter(Client.name == self.name).first()
            assert name is not None, f"User {self.name} not in DB!"

            yield name

            name.last_updated = func.now()

            try:
                db.add(name)
            except:
                log.print_fail("Failed to store db item!")

    @contextmanager
    def item(self, nc_code: str) -> T.Iterator[Item]:
        with ManagedSession() as db:
            item = db.query(Item).filter(Item.nc_code == nc_code).first()
            assert item is not None, f"Item for {nc_code} not in DB!"

            yield item

            try:
                db.add(item)
            except:
                log.print_fail("Failed to store db item!")

    @staticmethod
    def get_client_names() -> T.List[str]:
        clients = []
        with ManagedSession() as db:
            clients_db = db.query(Client).all()
            clients = [c.name for c in clients_db]
        return clients

    @staticmethod
    def add_client(
        name: str,
        email: str,
        phone_number: str,
        db_str: str = DEFAULT_DB,
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.name == name).first()
            if client is not None:
                log.print_warn(f"Skipping {name} add, already in db")
                return

            log.print_ok_arrow(f"Created {name} client")

            client = Client(
                name=name, email=email, phone_number=phone_number, last_updated=func.now()
            )

            db.add(client)

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
        db_str: str = DEFAULT_DB,
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.name == name).first()
            if client is None:
                log.print_fail(f"Failed to add item, user doesn't exist!")
                return

            if nc_code in [i.nc_code for i in client.items]:
                log.print_warn(f"Skipping add item, already in client!")
                return

            log.print_ok_arrow(f"Created item [{nc_code}] for {client.name}")

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

            db.add(item)
