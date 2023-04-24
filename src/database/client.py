import dotenv
import time
import typing as T

from contextlib import contextmanager
from sqlalchemy.sql import func

from database.connect import ManagedSession
from database.models.client import Client
from database.models.item import Item
from utils import logger

DEFAULT_DB = os.environ.get("DEFAULT_DB")


class ClientDb:
    def __init__(self, name: str, db_str: str = DEFAULT_DB) -> None:
        self.name = name
        self.items: T.List[Item] = []
        self.db_str = db_str

        with ManagedSession(self.db_str) as db:
            client = db.query(Client).filter(Client.name == name).first()
            assert client is not None, f"Client {self.name} not in DB!"
            logger.print_bold(f"{name} initiated")
            for item in client.items:
                self.items.append(item)

    @contextmanager
    def client(self) -> T.Iterator[Client]:
        with ManagedSession(self.db_str) as db:
            name = db.query(Client).filter(Client.name == self.name).first()
            assert name is not None, f"User {self.name} not in DB!"

            yield name

            try:
                db.add(name)
            except:
                logger.print_fail("Failed to store db item!")

    @contextmanager
    def item(self, nc_code: str) -> T.Iterator[Item]:
        with ManagedSession(self.db_str) as db:
            item = db.query(Item).filter(Item.nc_code == nc_code).first()
            assert item is not None, f"Item for {nc_code} not in DB!"

            yield item

            try:
                db.add(item)
            except:
                logger.print_fail("Failed to store db item!")

    @staticmethod
    def add_client(
        name: str,
        email: str,
        phone_number: str,
        db_str: str = DEFAULT_DB,
    ) -> None:
        with ManagedSession(db_str) as db:
            client = db.query(Client).filter(Client.name == name).first()
            if client is not None:
                logger.print_warn(f"Skipping {name} add, already in db")
                return

            logger.print_ok_arrow(f"Created {name} client")

            client = Client(
                name=name, email=email, phone_number=phone_number, last_updated=func.now()
            )

            db.add(client)

    @staticmethod
    def add_item(
        name: str,
        nc_code: str,
        brand_name: str,
        total_available: int,
        size: str,
        cases_per_pallet: int,
        supplier: str,
        supplier_allotment: int,
        broker_name: str,
        db_str: str = DEFAULT_DB,
    ) -> None:
        with ManagedSession(db_str) as db:
            client = db.query(Client).filter(Client.name == name).first()
            if client is None:
                logger.print_fail(f"Failed to add item, user doesn't exist!")
                return

            if nc_code in [i.nc_code for i in client.items]:
                logger.print_warn(f"Skipping add item, already in client!")
                return

            logger.print_ok_arrow(f"Created {nc_code} wallet for {client.name}")

            item = Item(
                client_id=client.name,
                nc_code=nc_code,
                brand_name=brand_name,
                total_available=total_available,
                size=size,
                cases_per_pallet=cases_per_pallet,
                supplier=supplier,
                supplier_allotment=supplier_allotment,
                broker_name=broker_name,
            )

            db.add(item)
