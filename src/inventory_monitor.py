import datetime
import json
import os
import shutil
import tempfile
import time
import typing as T

import pandas as pd

from database.client import ClientDb
from database.helpers import add_or_update_item
from database.models.client import Client, ClientSchema
from database.models.item import ItemSchema
from firebase.firebase_client import FirebaseClient
from util import email, log, wait, web2_client
from util.format import get_pretty_seconds
from util.twilio_util import TwilioUtil

STOCK_EMOJI = "\U0001F37A"


class InventoryMonitor:
    TIME_BETWEEN_INVENTORY_CHECKS = {
        "prod": 60 * 2,
        "test": 30,
    }
    TIME_BETWEEN_FIREBASE_QUERIES = {
        "prod": 60 * 15,
        "test": 60,
    }
    WAIT_TIME = 30
    INVENTORY_CODE_KEY = "NC Code"

    def __init__(
        self,
        download_url: str,
        download_key: str,
        twilio_util: TwilioUtil,
        admin_email: T.Optional[email.Email],
        log_dir: str,
        credentials_file: str,
        use_local_db: bool = False,
        inventory_csv_file: str = "",
        time_between_inventory_checks: T.Optional[int] = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.download_url = download_url
        self.download_key = download_key
        self.twilio_util: TwilioUtil = twilio_util
        self.email: T.Optional[email.Email] = admin_email
        self.csv_file = inventory_csv_file or os.path.join(log_dir, "inventory.csv")
        self.use_local_db = use_local_db
        self.dry_run = dry_run
        self.verbose = verbose

        self.mode = "prod" if not dry_run else "test"

        self.time_between_inventory_checks = (
            time_between_inventory_checks or self.TIME_BETWEEN_INVENTORY_CHECKS[self.mode]
        )

        self.clients: T.Dict[str, ClientSchema] = {}
        self.db = None

        self.last_inventory: T.Optional[pd.core.frame.DataFrame] = None
        self.new_inventory: T.Optional[pd.core.frame.DataFrame] = None

        self.web = web2_client.Web2Client()

        self.last_inventory_update_time: T.Optional[float] = None
        self.last_query_firebase_time: T.Optional[float] = None

        self.firebase_client: FirebaseClient = (
            FirebaseClient(credentials_file, verbose) if not use_local_db else None
        )

    def init(self, csv_file: str = "") -> None:
        csv_file = csv_file or self.csv_file

        self._update_cache_from_local_db()

        if os.path.isfile(csv_file):
            log.print_ok(f"Found existing inventory file at {csv_file}")
            self.new_inventory = self._clean_inventory(csv_file)
            self.last_inventory = self.new_inventory.copy()

    def _update_cache_from_local_db(self) -> None:
        client_names = ClientDb.get_client_names()
        log.print_ok(f"Found {len(client_names)} clients in local database")
        for name in client_names:
            with ClientDb.client(name) as client:
                if client is not None:
                    self.clients[name] = ClientSchema().dump(client)

    def _is_time_to_check_inventory(self) -> bool:
        if self.last_inventory_update_time is None:
            return True

        time_since_last_update = time.time() - self.last_inventory_update_time
        return time_since_last_update > self.time_between_inventory_checks

    def _update_local_db_item(self, client_name: str, item: pd.core.frame.DataFrame) -> None:
        # check and add item into db if not there already
        with ClientDb(client_name).item(item[self.INVENTORY_CODE_KEY]) as db:
            if db is None:
                add_or_update_item(client_name, item[self.INVENTORY_CODE_KEY])

        # update item in db
        with ClientDb(client_name).item(item[self.INVENTORY_CODE_KEY]) as db:
            db.brand_name = item["Brand Name"]
            db.total_available = int(item["Total Available"])
            db.size = item["Size"]
            db.cases_per_pallet = int(item["Cases Per Pallet"])
            db.supplier = item["Supplier"]
            db.supplier_allotment = int(item["Supplier Allotment"])
            db.broker_name = item["Broker Name"]

    def _check_and_see_if_firebase_should_be_updated(self) -> None:
        if self.firebase_client is None:
            return

        update_from_firebase = False
        if self.last_query_firebase_time is None:
            update_from_firebase = True
        else:
            time_since_last_update = time.time() - self.last_query_firebase_time
            update_from_firebase = (
                time_since_last_update > self.TIME_BETWEEN_FIREBASE_QUERIES[self.mode]
            )

        if update_from_firebase:
            self.last_query_firebase_time = time.time()
            self.firebase_client.update_watchers()
        else:
            time_till_next_update = (
                self.TIME_BETWEEN_FIREBASE_QUERIES[self.mode] - time_since_last_update
            )
            log.print_normal(
                f"Next firebase manual refresh in {get_pretty_seconds(time_till_next_update)}"
            )

        for id, client in self.clients.items():
            for item in client["items"]:
                self.firebase_client.check_and_maybe_update_to_firebase(id, item["nc_code"])

        self.firebase_client.check_and_maybe_handle_firebase_db_updates()

    def check_client_inventory(self, client: ClientSchema) -> None:
        if self.verbose:
            log.print_bold(f"Checking {json.dumps(client, indent=4)}")

        if not client:
            return

        with ClientDb.client(client["id"]) as db:
            if db is None:
                return
            db.last_updated = datetime.datetime.fromtimestamp(self.last_inventory_update_time)

        items_to_update = []

        self.twilio_util.set_ignore_time_window(not client["alert_range_enabled"])

        for item_schema in client["items"]:
            nc_code = item_schema["nc_code"]

            if nc_code is None:
                continue

            log.print_ok_arrow(f"Checking {nc_code}")

            if not item_schema["is_tracking"]:
                log.print_normal_arrow(f"Skipping {nc_code} because it is not being tracked")
                continue

            item: pd.core.frame.DataFrame = self._get_item_from_inventory(
                item_schema, self.new_inventory
            )

            if item is None:
                log.print_normal_arrow(f"Did not find {nc_code} in inventory")
                continue

            self._update_local_db_item(client["id"], item)

            if item["Total Available"] == 0:
                log.print_normal_arrow(f"{nc_code} is out of stock")
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
                delta_str = log.format_ok(f"+{delta}")
            elif delta < 0:
                delta_str = log.format_fail(f"{delta}")
            else:
                delta_str = log.format_normal(f"{delta}")

            brand_name = item["Brand Name"]

            if self.verbose:
                log.print_ok_blue_arrow(
                    f"{nc_code}: Previous inventory: {previous_available}, Current inventory: {item['Total Available']}"
                )
            log.print_ok_blue_arrow(
                f"{STOCK_EMOJI} {nc_code} {brand_name} change: {delta_str} units"
            )

            if previous_item is not None and previous_available != 0:
                if self.verbose:
                    log.print_normal_arrow(f"No alert, {nc_code} was previously in stock")
                continue

            inventory_threshold = client["threshold_inventory"]

            if delta < inventory_threshold:
                if self.verbose:
                    log.print_normal_arrow(
                        f"{nc_code} is below inventory threshold of {inventory_threshold}"
                    )
                continue

            items_to_update.append((nc_code, brand_name, item["Total Available"]))

        message = f"NC ABC Inventory Alert\n"

        for info in items_to_update:
            nc_code, brand_name, total_available = info
            message += (
                f"{STOCK_EMOJI} {nc_code}: {brand_name} is now in stock with {total_available}\n\n"
            )

            with ClientDb.client(client["id"]) as db:
                if db is None:
                    break
                db.updates_sent += 1

        if not items_to_update:
            if self.verbose:
                log.print_normal_arrow("No items to update, not sending any alerts")
            return

        log.print_ok(message)

        if self.dry_run:
            log.print_normal_arrow("Dry run, not sending SMS")
            return

        if not item_schema or not item_schema["is_tracking"]:
            log.print_normal_arrow("Not sending alert, item is not being tracked")
            return

        if client["phone_number"] and client["phone_alerts"]:
            self.twilio_util.send_sms_if_in_window(
                client["phone_number"],
                message,
            )

        if client["email"] and client["email_alerts"] and self.email:
            email.send_email(
                emails=[self.email],
                to_addresses=[client["email"]],
                subject="{STOCK_EMOJI} NC ABC Inventory Alert",
                content=message,
            )

    def _get_item_from_inventory(
        self, item: ItemSchema, dataframe: pd.core.frame.DataFrame
    ) -> T.Optional[pd.core.frame.DataFrame]:
        if dataframe is None or dataframe.empty:
            log.print_warn("No inventory loaded")
            return None

        inventory_codes = dataframe[self.INVENTORY_CODE_KEY]

        nc_code = item["nc_code"]

        matches: pd.core.frame.DataFrame = dataframe[inventory_codes == nc_code]

        if matches.empty:
            log.print_warn(f"Did not find {nc_code} in inventory")
            return None

        return matches.iloc[0]

    def _clean_inventory(self, csv_file: str) -> pd.core.frame.DataFrame:
        try:
            dataframe = pd.read_csv(csv_file)
        except pd.errors.EmptyDataError:
            log.print_fail("Empty inventory file")
            return None

        # clean up the code column
        dataframe[self.INVENTORY_CODE_KEY] = dataframe[self.INVENTORY_CODE_KEY].str.replace(
            r"=\"(.*)\"", r"\1", regex=True
        )

        return dataframe

    def update_inventory(self, download_url: str) -> pd.core.frame.DataFrame:
        if self.new_inventory is not None:
            self.last_inventory = self.new_inventory.copy()

        log.format_bright(f"Updating inventory from {download_url}")

        with tempfile.NamedTemporaryFile() as csv_file:
            if os.path.isfile(download_url):
                shutil.copyfile(download_url, csv_file.name)
            elif self._is_time_to_check_inventory():
                try:
                    self.web.url_download(
                        download_url, csv_file.name, self.download_key, timeout=30.0
                    )
                except Exception as e:
                    log.print_fail(f"Error getting inventory: {e}")

            inventory = self._clean_inventory(csv_file.name)

            if inventory is None:
                return None

            self.new_inventory = inventory
            log.print_ok_arrow(f"Downloaded {len(self.new_inventory)} items")
            shutil.copy(csv_file.name, self.csv_file)

        # iterate through all items in the new_inventory and add them to the database
        for _, item in self.new_inventory.iterrows():
            self._update_local_db_item("", item)

        self.last_inventory_update_time = time.time()

        return self.new_inventory

    def _check_inventory(self) -> None:
        self._update_cache_from_local_db()

        if not self.clients:
            log.print_fail("No clients to check inventory for")
            return

        for name, client in self.clients.items():
            log.print_bold(f"{'─' * 80}")
            log.print_bold(f"Checking inventory for {name}...")
            self.check_client_inventory(client)
            with ClientDb.client(name) as db:
                if db is None:
                    break
                if db.alert_time_range_end and db.alert_time_range_start and db.alert_time_zone:
                    self.twilio_util.update_send_window(
                        db.alert_time_range_start, db.alert_time_range_end, db.alert_time_zone
                    )

        log.print_bold(f"{'─' * 80}")

        self._check_and_see_if_firebase_should_be_updated()
        self.twilio_util.check_sms_queue()

    def run(self) -> None:
        self.update_inventory(self.download_url)

        self._check_inventory()

        wait.wait(self.WAIT_TIME)
