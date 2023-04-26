import json
import os
import shutil
import tempfile
import time
import typing as T

import pandas as pd

from database.client import ClientDb
from database.models.client import Client, ClientSchema
from database.models.item import Item, ItemSchema
from util import log, wait, web2_client
from util.twilio_util import TwilioUtil


class InventoryMonitor:
    TIME_BETWEEN_INVENTORY_CHECKS = 60 * 2
    WAIT_TIME = 60
    INVENTORY_CODE_KEY = "NC Code"

    def __init__(
        self,
        download_url: str,
        download_key: str,
        twilio_util: TwilioUtil,
        log_dir: str,
        use_local_db: bool = False,
        time_between_inventory_checks: int = None,
        dry_run: bool = False,
    ) -> None:
        self.download_url = download_url
        self.download_key = download_key
        self.twilio_util: TwilioUtil = twilio_util
        self.csv_file = os.path.join(log_dir, "inventory.csv")
        self.use_local_db = use_local_db
        self.time_between_inventory_checks = (
            time_between_inventory_checks or self.TIME_BETWEEN_INVENTORY_CHECKS
        )
        self.dry_run = dry_run

        self.clients: T.List[str, ClientSchema] = {}
        self.db = None

        self.last_inventory = pd.core.frame.DataFrame | None
        self.new_inventory = pd.core.frame.DataFrame | None

        self.web = web2_client.Web2Client()

        self.last_inventory_update_time = None

    def init(self) -> None:
        if self.use_local_db:
            client_names = ClientDb.get_client_names()
            log.print_ok(f"Found {len(client_names)} clients in local database")
            for name in client_names:
                db = ClientDb(name)
                with db.client() as client:
                    self.clients[name] = ClientSchema().dump(client)

        if os.path.isfile(self.csv_file):
            self.last_inventory = self._load_inventory(self.csv_file)

    def _is_time_to_check_inventory(self) -> bool:
        if self.last_inventory_update_time is None:
            return True

        time_since_last_update = time.time() - self.last_inventory_update_time
        return time_since_last_update > self.time_between_inventory_checks

    def _update_local_db_item(self, client_name: str, item: pd.core.frame.DataFrame) -> None:
        if not self.use_local_db:
            return

        with ClientDb(client_name).client() as db:
            for db_item in db.items:
                if db_item.nc_code != item[self.INVENTORY_CODE_KEY]:
                    continue

                db_item.brand_name = item["Brand Name"]
                db_item.total_available = int(item["Total Available"])
                db_item.size = item["Size"]
                db_item.cases_per_pallet = int(item["Cases Per Pallet"])
                db_item.supplier = item["Supplier"]
                db_item.supplier_allotment = int(item["Supplier Allotment"])
                db_item.broker_name = item["Broker Name"]

    def check_client_inventory(self, client: ClientSchema) -> bool:
        log.print_bold(f"Checking {json.dumps(client, indent=4)}")

        if not client:
            return False

        for item_schema in client["items"]:
            nc_code = item_schema["nc_code"]

            log.print_ok_arrow(f"Checking {nc_code}")

            if nc_code is None:
                continue

            item: pd.core.frame.DataFrame = self._get_item_from_inventory(
                item_schema, self.new_inventory
            )

            if item is None:
                log.print_normal(f"Did not find {nc_code} in inventory")
                continue

            self._update_local_db_item(client["name"], item)

            if item["Total Available"] == 0:
                log.print_normal(f"{nc_code} is out of stock")
                continue

            previous_item: pd.core.frame.DataFrame = self._get_item_from_inventory(
                item_schema, self.last_inventory
            )

            if previous_item is None:
                log.print_fail(f"{nc_code} was not previously in inventory")
                previous_available = 0
            else:
                previous_available = previous_item["Total Available"]

            delta = item["Total Available"] - previous_available
            if delta > 0:
                delta_str = log.format_ok_blue_arrow(f"+{delta}")
            elif delta < 0:
                delta_str = log.format_fail_arrow(f"{delta}")
            else:
                delta_str = log.format_normal(f"{delta}")

            brand_name = item["Brand Name"]

            log.print_ok_blue(
                f"{nc_code}: Previous inventory: {previous_available}, Current inventory: {item['Total Available']}"
            )
            log.print_ok_blue_arrow(f"{nc_code} {brand_name} change: {delta_str} units")

            if previous_item is not None and previous_available != 0:
                log.print_normal(f"No alert, {nc_code} was previously in stock")
                continue

            inventory_threshold = client["inventory_threshold"]

            if delta < inventory_threshold:
                log.print_normal(f"{nc_code} is below inventory threshold of {inventory_threshold}")
                continue

            message = f"ABC NC Inventory Alert\n"
            message += f"{nc_code}: {brand_name} is now in stock with {item['Total Available']}"

            log.print_ok_arrow(message)

            if self.dry_run:
                log.print_normal("Dry run, not sending SMS")
                return True

            if client.phone_number is not None:
                self.twilio_util.send_sms(
                    client.phone_number,
                    message,
                )

            return True

    def _get_item_from_inventory(
        self, item: ItemSchema, dataframe: pd.core.frame.DataFrame
    ) -> pd.core.frame.DataFrame | None:
        inventory_codes = dataframe[self.INVENTORY_CODE_KEY]

        nc_code = item["nc_code"]

        matches: pd.core.frame.DataFrame = dataframe[inventory_codes == nc_code]

        if matches.empty:
            log.print_warn(f"Did not find {nc_code} in inventory")
            return None

        return matches.iloc[0]

    def _load_inventory(self, csv_file: str) -> pd.core.frame.DataFrame:
        dataframe = pd.read_csv(csv_file)

        # clean up the code column
        dataframe[self.INVENTORY_CODE_KEY] = dataframe[self.INVENTORY_CODE_KEY].str.replace(
            r"=\"(.*)\"", r"\1", regex=True
        )

        return dataframe

    def update_inventory(self, download_url: str) -> pd.core.frame.DataFrame:
        with tempfile.NamedTemporaryFile() as csv_file:
            if os.path.isfile(download_url):
                shutil.copyfile(download_url, csv_file.name)
            else:
                try:
                    self.web.url_download(
                        download_url, csv_file.name, self.download_key, timeout=30.0
                    )
                except Exception as e:
                    log.print_fail(f"Error getting inventory: {e}")

            self.new_inventory: pd.core.frame.DataFrame = self._load_inventory(csv_file.name)
            shutil.copy(csv_file.name, self.csv_file)

        self.last_inventory_update_time = time.time()

        return self.new_inventory

    def _check_inventory(self) -> None:
        if not self.clients:
            log.print_fail("No clients to check inventory for")
            return

        self.update_inventory(self.download_url)

        for name, client in self.clients.items():
            log.print_normal(f"Checking inventory for {name}")
            self.check_client_inventory(client)

        self.last_inventory = self.new_inventory

    def run(self) -> None:
        if not self._is_time_to_check_inventory():
            return
        self._check_inventory()
