import datetime
import os
import time
import typing as T
from contextlib import contextmanager

import dotenv
from sqlalchemy.sql import func

from database.connect import ManagedSession
from database.models.client import Client, PhoneNumber, TrackingItem
from database.models.item import Item, ItemSchema
from database.models.item_association import ItemAssociationTable
from util import log

dotenv.load_dotenv(".env")
DEFAULT_DB = os.environ.get("DEFAULT_DB", "client.db")


class ClientDb:
    @staticmethod
    @contextmanager
    def client(client: str) -> T.Iterator[Client]:
        with ManagedSession() as db:
            name = db.query(Client).filter(Client.id == client).first()

            yield name

            if name is None:
                return

            name.last_updated = func.now()

            db.add(name)

    @staticmethod
    @contextmanager
    def item(nc_code: str) -> T.Iterator[Item]:
        with ManagedSession() as db:
            item = db.query(Item).filter(Item.id == nc_code).first()

            yield item

            if item is None:
                return

            db.add(item)

    @staticmethod
    @contextmanager
    def tracking_item(client: str, nc_code: str) -> T.Iterator[TrackingItem]:
        with ManagedSession() as db:
            tracking_item = (
                db.query(TrackingItem)
                .filter(TrackingItem.client_id == client)
                .filter(TrackingItem.nc_code == nc_code)
                .first()
            )

            yield tracking_item

            if tracking_item is None:
                return

            db.add(tracking_item)

    @staticmethod
    def get_client_names() -> T.List[str]:
        clients = []
        with ManagedSession() as db:
            clients_db = db.query(Client).all()
            clients = [c.id for c in clients_db]
        return clients

    @staticmethod
    def add_track_item(name: str, nc_code: str, do_track: bool = True) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                return
            tracking_item = (
                db.query(TrackingItem)
                .filter(TrackingItem.client_id == name)
                .filter(TrackingItem.nc_code == nc_code)
                .first()
            )
            if tracking_item is None and do_track:
                tracking_item = TrackingItem(client_id=client.id, nc_code=nc_code)
                db.add(tracking_item)
            elif tracking_item is not None and not do_track:
                db.query(TrackingItem).filter(TrackingItem.client_id == name).filter(
                    TrackingItem.nc_code == nc_code
                ).delete()

    @staticmethod
    def delete_track_item(name: str, nc_code: str) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                return
            tracking_item = (
                db.query(TrackingItem)
                .filter(TrackingItem.client_id == client.id)
                .filter(TrackingItem.nc_code == nc_code)
                .first()
            )
            if tracking_item is not None:
                db.delete(tracking_item)

    @staticmethod
    def delete_item_association(name: str, nc_code: str) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                log.print_warn(f"Not deleting {nc_code}, {name} not in db")
                return
            if nc_code not in [i.id for i in client.items]:
                log.print_warn(f"Not deleting {nc_code}, it's not in client items")
                return

            item = db.query(Item).filter(Item.id == nc_code).first()
            if item is None:
                log.print_warn(f"Not deleting {nc_code}, it's not in items db")
                return
            client.items.remove(item)

    @staticmethod
    def delete_client(name: str, verbose: bool = False) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                if verbose:
                    log.print_warn(f"Not deleting {name}, it's not in db")
                return

            db.query(TrackingItem).filter(TrackingItem.client_id == client.id).delete()
            db.query(Client).filter(Client.id == name).delete()

    @staticmethod
    def add_client(
        name: str,
        email: str = "",
        phone_numbers: T.List[str] = None,
        verbose: bool = False,
    ) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is not None:
                if verbose:
                    log.print_warn(f"Skipping {name} add, already in db")
                return

            log.print_ok_arrow(f"Created {name} client")

            if phone_numbers is None:
                phone_numbers = []

            phone_number_objects = []

            for phone_number in phone_numbers:
                phone = PhoneNumber(number=phone_number)
                phone_number_objects.append(phone)

            client = Client(
                id=name, email=email, phone_numbers=phone_number_objects, last_updated=func.now()
            )

            db.add(client)

    @staticmethod
    def add_phone_numbers(name: str, phone_numbers: T.List[str]) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == name).first()
            if client is None:
                return

            client.phone_numbers = []
            for phone_number in phone_numbers:
                phone = PhoneNumber(number=phone_number)
                client.phone_numbers.append(phone)

            db.add(client)

    @staticmethod
    def delete_item(nc_code: str, verbose: bool = False) -> None:
        with ManagedSession() as db:
            item = db.query(Item).filter(Item.id == nc_code).first()
            if item is None:
                if verbose:
                    log.print_warn(f"Not deleting {nc_code}, nothing to delete")
            else:
                db.query(Item).filter(Item.id == nc_code).delete()

    @staticmethod
    def add_or_update_item(
        nc_code: str,
        brand_name: str = None,
        total_available: int = None,
        size: str = None,
        cases_per_pallet: int = None,
        supplier: str = None,
        supplier_allotment: int = None,
        broker_name: str = None,
        out_of_stock_time: T.Optional[datetime.datetime] = None,
        verbose: bool = False,
    ) -> bool:
        is_new = False
        with ManagedSession() as db:
            item = db.query(Item).filter(Item.id == nc_code).first()

            if item is None:
                item = Item(
                    id=nc_code,
                )
                log.print_ok_arrow(f"Created item [{nc_code}]")
                is_new = True
            elif verbose:
                log.print_ok_arrow(f"Updated item [{nc_code}]")

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
            if out_of_stock_time is not None:
                item.out_of_stock_time = out_of_stock_time

            db.add(item)

        return is_new

    @staticmethod
    def add_item_to_client(client: str, nc_code: str) -> None:
        with ManagedSession() as db:
            client = db.query(Client).filter(Client.id == client).first()
            item = db.query(Item).filter(Item.id == nc_code).first()
            if client is None or item is None:
                return
            if item in client.items:
                return
            log.print_ok_arrow(f"Added {nc_code} to {client.id}")
            client.items.append(item)

    @staticmethod
    def add_item_to_client_and_track(client: str, nc_code: str) -> None:
        ClientDb.add_or_update_item(nc_code)
        ClientDb.add_item_to_client(client, nc_code)
        ClientDb.add_track_item(client, nc_code, True)

    @staticmethod
    def all_items() -> T.Dict[str, ItemSchema]:
        with ManagedSession() as db:
            items = db.query(Item).all()
            return {i.id: ItemSchema().dump(i) for i in items}
