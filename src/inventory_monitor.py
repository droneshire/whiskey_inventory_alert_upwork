import datetime
import gc
import json
import os
import shutil
import tempfile
import time
import typing as T

import deepdiff
import pandas as pd
from sqlalchemy.exc import IntegrityError

from database.client import ClientDb
from database.models.client import ClientSchema
from firebase.firebase_client import FirebaseClient
from headers import HEADERS
from util import email, log, wait, web2_client
from util.file_util import make_sure_path_exists
from util.format import get_pretty_seconds
from util.twilio_util import TwilioUtil

STOCK_EMOJI = "\U0001F943"


def _sanitize_column_name(name: str) -> str:
    # Convert to lowercase
    sanitized_name = name.lower()

    # Replace spaces with underscores
    sanitized_name = sanitized_name.replace(" ", "_")

    # Remove special characters (anything that's not alphanumeric or underscore)
    sanitized_name = "".join(char for char in sanitized_name if char.isalnum() or char == "_")

    return sanitized_name


class InventoryMonitor:
    DOWNLOAD_URL = "https://abc2.nc.gov/StoresBoards/ExportData"
    DOWNLOAD_KEY = ""

    TIME_BETWEEN_INVENTORY_CHECKS = {
        "prod": 60 * 5,
        "test": 30,
    }
    TIME_BETWEEN_FIREBASE_QUERIES = {
        "prod": 60 * 15,
        "test": 60,
    }
    WAIT_TIME = 30
    RAW_INVENTORY_CODE_KEY = "NC Code"
    INVENTORY_CODE_KEY = _sanitize_column_name(RAW_INVENTORY_CODE_KEY)
    MAX_DELTA_IN_INVENTORY_COUNT = 2
    MAX_INVENTORY_DOWNLOADS_WITHOUT_CHANGE = 10
    MAX_CHARS_PER_MESSAGE = 1600
    MAX_ITEMS_PER_MESSAGE = 20

    def __init__(
        self,
        twilio_util: T.Optional[TwilioUtil],
        admin_email: T.Optional[email.Email],
        log_dir: str,
        credentials_file: str,
        allowlist_clients: T.Optional[T.List[str]] = None,
        use_local_db: bool = False,
        inventory_csv_file: str = "",
        inventory_diff_file: str = "",
        time_between_inventory_checks: T.Optional[int] = None,
        enable_inventory_delta_file: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.download_url = self.DOWNLOAD_URL
        self.twilio_util: T.Optional[TwilioUtil] = twilio_util
        self.email: T.Optional[email.Email] = admin_email
        self.csv_file = inventory_csv_file or os.path.join(log_dir, "inventory.csv")
        self.inventory_change_file = inventory_diff_file or os.path.join(
            log_dir, "inventory_changes.json"
        )
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

        self.skip_alerts = False

        self.web = web2_client.Web2Client()

        self.last_inventory_update_time: T.Optional[float] = None
        self.last_query_firebase_time: T.Optional[float] = None
        self.last_valid_inventory_download_size = 0
        self.inventory_downloads_without_change = 0
        self.last_inventory_download_size = 0

        self.enable_inventory_delta_file = enable_inventory_delta_file

        self.firebase_client: FirebaseClient = (
            FirebaseClient(credentials_file, verbose) if not use_local_db else None
        )

        self.allowlist_clients = allowlist_clients

    def init(self, csv_file: str = "") -> None:
        csv_file = csv_file or self.csv_file

        self._update_cache_from_local_db()

        # Check if the CSV file exists and is not empty
        if os.path.isfile(csv_file):
            log.print_ok(f"Found existing inventory file at {csv_file}")

            # Clean the inventory
            cleaned_inventory = self._clean_inventory(csv_file)

            # Check if the cleaned inventory is not None and not empty
            if cleaned_inventory is not None and not cleaned_inventory.empty:
                self.new_inventory = cleaned_inventory

                # Create a copy for last_inventory
                self.last_inventory = self.new_inventory.copy()
            else:
                log.format_fail_arrow(f"Failed to load or clean inventory from {csv_file}")
                self.new_inventory = None
                self.last_inventory = None

        if self.new_inventory is None:
            log.format_fail_arrow("Inventory doesn't exist, skipping alerts")
            self.skip_alerts = True

    def _update_cache_from_local_db(self) -> None:
        client_names = ClientDb.get_client_names()
        log.print_ok(f"Found {len(client_names)} clients in local database")
        for name in client_names:
            with ClientDb.client(name) as client:
                if client is not None:
                    self.clients[name] = ClientSchema().dump(client)

    def _is_time_to_check_inventory(self, now: float) -> bool:
        if self.last_inventory_update_time is None:
            return True

        time_since_last_update = now - self.last_inventory_update_time
        time_till_next_update = get_pretty_seconds(
            self.time_between_inventory_checks - time_since_last_update
        )
        log.print_normal(f"Time till inventory update: {time_till_next_update}")
        return time_since_last_update > self.time_between_inventory_checks

    def _update_local_db_item(
        self,
        client_name: str,
        item: pd.core.frame.Series,  # Note that we're changing this to Series to reflect the datatype
        now: T.Optional[datetime.datetime] = None,
    ) -> bool:
        # check and add item into db if not there already, returns true if it is a new item

        now = now or datetime.datetime.now(datetime.timezone.utc)

        inventory = int(item.total_available)
        nc_code = getattr(item, self.INVENTORY_CODE_KEY)

        return ClientDb.add_or_update_item(
            nc_code,
            brand_name=item.brand_name,
            total_available=inventory,
            size=item.size,
            cases_per_pallet=int(item.cases_per_pallet),
            supplier=item.supplier,
            supplier_allotment=int(item.supplier_allotment),
            broker_name=item.broker_name,
            out_of_stock_time=None if inventory > 0 else now,
        )

    def _set_inventory_to_zero(self, nc_code: str) -> None:
        ClientDb.add_or_update_item(nc_code, total_available=0)

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
                self.firebase_client.check_and_maybe_update_to_firebase(id, item["id"])

        self.firebase_client.check_and_maybe_handle_firebase_db_updates()

    def _check_outside_of_out_of_stock_window(
        self,
        client_time_out_of_stock_hours: int,
        nc_code: int,
        now: T.Optional[datetime.datetime] = None,
    ) -> bool:
        if client_time_out_of_stock_hours == 0:
            return False

        now = now or datetime.datetime.utcnow()

        with ClientDb.item(nc_code) as db:
            if db is None:
                return False

            out_of_stock_time = db.out_of_stock_time

        if out_of_stock_time is None:
            return False

        time_out_of_stock = now - out_of_stock_time
        time_out_of_stock_hours = time_out_of_stock.total_seconds() / 3600

        log.print_bright(
            f"{nc_code} has been out of stock for {time_out_of_stock_hours}h {client_time_out_of_stock_hours}h"
        )
        if time_out_of_stock_hours <= client_time_out_of_stock_hours:
            log.print_warn(
                f"{nc_code} has not been out of stock long enough: {time_out_of_stock_hours}"
            )
            return True

        return False

    def check_client_untracked_new_inventory(
        self, client: ClientSchema, new_items: T.List[T.Tuple[str, str, int]] = None
    ) -> None:
        should_update_new_data = client["update_on_new_data"]

        if not should_update_new_data:
            log.print_normal_arrow("Not checking new inventory because client has disabled it")
            return

        if new_items is None:
            log.print_normal_arrow("No new items to check")
            return

        log.print_bright(f"Checking {len(new_items)} new items...")

        items_to_update = [i for i in new_items if i not in client["items"]]
        self._maybe_send_alerts(client, new_items, is_new_inventory=True)

    def check_client_inventory(
        self, client: ClientSchema, now: T.Optional[datetime.datetime] = None
    ) -> None:
        if self.verbose:
            log.print_bold(f"Checking {json.dumps(client, indent=4)}")

        if not client:
            return

        now = now or datetime.datetime.utcnow()

        with ClientDb.client(client["id"]) as db:
            if db is None:
                return
            if self.last_inventory_update_time:
                db.last_updated = datetime.datetime.fromtimestamp(self.last_inventory_update_time)

        items_to_update = []

        if self.twilio_util:
            for phone_number in client["phone_numbers"]:
                self.twilio_util.set_ignore_time_window(
                    phone_number["number"], not client["alert_range_enabled"]
                )

        client_items = {i["id"]: i for i in client["items"]}
        log.print_bright(f"Checking {len(client_items.keys())} items...")

        for nc_code, item_schema in client_items.items():
            if self.verbose:
                log.print_ok_arrow(f"Checking {nc_code}")

            items_tracking = [t["nc_code"] for t in client["tracked_items"]]
            if nc_code not in items_tracking:
                log.print_normal_arrow(f"Skipping {nc_code} because it is not being tracked")
                continue

            item_df: pd.core.series.Series = self._get_item_from_inventory(
                item_schema["id"], self.new_inventory
            )

            if item_df is None:
                self._set_inventory_to_zero(nc_code)
                continue

            self._update_local_db_item(client["id"], item_df, now)

            if item_df.total_available == 0:
                if self.verbose:
                    log.print_normal_arrow(f"{nc_code} is out of stock")
                continue

            previous_item: pd.core.series.Series = self._get_item_from_inventory(
                item_schema["id"], self.last_inventory
            )

            if previous_item is None:
                log.print_fail(f"{nc_code} was not previously in inventory")
                previous_available = 0
            else:
                previous_available = previous_item.total_available

            delta = item_df.total_available - previous_available
            if delta > 0:
                delta_str = log.format_ok(f"+{delta}")
            elif delta < 0:
                delta_str = log.format_fail(f"{delta}")
            else:
                delta_str = log.format_normal(f"{delta}")

            brand_name = item_df.brand_name

            if self.verbose or delta != 0:
                log.print_normal_arrow(
                    f"{nc_code}: Previous inventory: {previous_available}, Current inventory: {item_df.total_available}"
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
                log.print_normal_arrow(
                    f"{nc_code} is below inventory threshold of {inventory_threshold}"
                )
                continue

            if self._check_outside_of_out_of_stock_window(
                client["min_hours_since_out_of_stock"], nc_code, now
            ):
                log.print_normal_arrow(f"{nc_code} is inside of out of stock window")
                continue

            if self.skip_alerts:
                continue

            items_to_update.append((nc_code, brand_name, item_df.total_available))

        self._maybe_send_alerts(client, items_to_update)

    def _is_client_allowed_to_send_sms(self, client_id: str) -> bool:
        if not self.allowlist_clients:
            return True

        return client_id in self.allowlist_clients

    def _maybe_send_alerts(
        self, client: ClientSchema, items_to_update: T.List[T.Tuple], is_new_inventory: bool = False
    ) -> None:
        message = "NC ABC Inventory Alert\n" if not is_new_inventory else "NC ABC New Item Alert\n"

        new_data_email_alerts = not is_new_inventory or client["enable_new_data_email_alert"]
        new_data_sms_alerts = not is_new_inventory or client["enable_new_data_sms_alert"]

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

        if not client["has_paid"]:
            log.print_warn("Not sending alert, client has not paid")
            return

        if (
            len(items_to_update) > self.MAX_ITEMS_PER_MESSAGE
            or len(message) > self.MAX_CHARS_PER_MESSAGE
        ):
            sms_message = (
                f"NC ABC Inventory Alert\n{STOCK_EMOJI}\n\n{len(items_to_update)} new items in stock\n"
                "Not texting full list since there were too many items updated at once.\n"
                "Please check your email for the full list.\n\n"
            )
        else:
            sms_message = message

        log.print_ok(sms_message)

        if self.dry_run:
            log.print_normal_arrow("Dry run, not sending SMS or email")
            return

        if not self._is_client_allowed_to_send_sms(client["id"]):
            log.print_normal_arrow("Client is not allowed to send SMS")
            return

        if (
            client["phone_numbers"]
            and client["phone_alerts"]
            and new_data_sms_alerts
            and self.twilio_util
        ):
            for phone_number in client["phone_numbers"]:
                self.twilio_util.send_sms_if_in_window(
                    phone_number["number"],
                    sms_message,
                )

        if client["email"] and client["email_alerts"] and new_data_email_alerts and self.email:
            email.send_email(
                emails=[self.email],
                to_addresses=[client["email"]],
                subject=f"{STOCK_EMOJI} NC ABC Inventory Alert",
                content=message,
                verbose=True,
            )

    def _df_to_real_json(self, dataframe: pd.core.frame.DataFrame) -> T.Dict[str, T.Any]:
        if dataframe is None:
            return {}
        df_json = json.loads(dataframe.to_json(orient="values"))
        new_json = {}
        for item in df_json:
            new_json[item[0]] = item[1:]
        return new_json

    def _write_inventory_delta_file(self) -> None:
        if not self.enable_inventory_delta_file:
            return

        new_json = self._df_to_real_json(self.new_inventory)
        last_json = self._df_to_real_json(self.last_inventory)

        diff = deepdiff.DeepDiff(last_json, new_json, ignore_order=True)
        if not diff:
            return
        data_json = {}
        diff_json = diff.to_json(indent=4, sort_keys=True, ensure_ascii=True)

        make_sure_path_exists(self.inventory_change_file)

        if os.path.exists(self.inventory_change_file):
            with open(self.inventory_change_file, "r") as infile:
                data = infile.read()
                if data:
                    data_json = json.loads(data)

        with open(self.inventory_change_file, "w") as outfile:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d--%H:%M:%S")
            data_json[timestamp] = json.loads(diff_json)
            json.dump(data_json, outfile, indent=4, sort_keys=True)

        log.print_normal(f"Changes in inventory:\n{diff_json}")

    def _get_item_from_inventory(
        self, nc_code: int, dataframe: pd.core.frame.DataFrame
    ) -> T.Optional[pd.Series]:
        if dataframe is None or dataframe.empty:
            log.print_warn("No inventory loaded")
            return None

        inventory_codes = dataframe[self.INVENTORY_CODE_KEY]
        matches: pd.core.frame.DataFrame = dataframe[inventory_codes == nc_code]

        if matches.empty:
            log.print_warn(f"Did not find {nc_code} in inventory")
            return None
        return matches.iloc[0]

    def _clean_inventory(self, csv_file: str) -> pd.core.frame.DataFrame:
        chunk_size = 4096
        processed_chunks = []

        try:
            with pd.read_csv(csv_file, chunksize=chunk_size) as reader:
                for chunk in reader:
                    # clean up the code column
                    chunk[self.RAW_INVENTORY_CODE_KEY] = chunk[self.RAW_INVENTORY_CODE_KEY].str.replace(
                        r"=\"(.*)\"", r"\1", regex=True
                    )
                    # Sanitize column names
                    chunk.columns = [_sanitize_column_name(col) for col in chunk.columns]

                    processed_chunks.append(chunk)
        except:
            log.print_fail(f"Error parsing inventory file")
            return None

        dataframe = pd.concat(processed_chunks, ignore_index=True)
        return dataframe

    def _is_inventory_valid(self, inventory: pd.core.frame.DataFrame) -> bool:
        if len(inventory) == 0:
            log.print_fail("No inventory found")
            self.last_inventory_update_time = time.time()
            return False

        if self.last_inventory_download_size == len(inventory):
            self.inventory_downloads_without_change += 1
        else:
            self.inventory_downloads_without_change = 0

        override_delta_requirement = (
            self.inventory_downloads_without_change > self.MAX_INVENTORY_DOWNLOADS_WITHOUT_CHANGE
        )

        self.last_inventory_download_size = len(inventory)

        change_in_inventory = self.last_valid_inventory_download_size - len(inventory)
        if (
            not override_delta_requirement
            and change_in_inventory >= self.MAX_DELTA_IN_INVENTORY_COUNT
        ):
            log.print_warn(
                f"Inventory size delta is too large: {change_in_inventory}. Not using inventory."
            )
            self.last_inventory_update_time = time.time()
            return False

        self.last_valid_inventory_download_size = len(inventory)
        self.inventory_downloads_without_change = 0
        return True

    def update_inventory(
        self,
        download_url: str,
        now: float = None,
        skip_db_add: bool = False,
    ) -> T.Optional[T.List[T.Tuple[str, str, int]]]:
        if self.new_inventory is not None:
            self.last_inventory = self.new_inventory
            self.new_inventory = None
            gc.collect()

        now = now or time.time()

        with tempfile.NamedTemporaryFile(suffix=".csv") as csv_file:
            if os.path.isfile(download_url):
                log.print_bold(f"Downloading inventory from {download_url}...")
                shutil.copyfile(download_url, csv_file.name)
            elif self._is_time_to_check_inventory(now):
                log.print_bold(f"Downloading inventory from {download_url}...")
                try:
                    self.web.url_download(
                        download_url, csv_file.name, headers=HEADERS, timeout=30.0
                    )
                except Exception as e:
                    log.print_fail(f"Error downloading inventory: {e}")
            else:
                log.print_normal_arrow("Not time to check inventory")
                self.new_inventory = self.last_inventory
                return None

            self.new_inventory = self._clean_inventory(csv_file.name)

            if self.new_inventory is None or self.new_inventory.empty:
                log.print_fail("Failed to download inventory")
                self.new_inventory = self.last_inventory
                return None

            if not self._is_inventory_valid(self.new_inventory):
                log.print_fail("Inventory is not valid, setting to last inventory")
                self.new_inventory = self.last_inventory
                return None

            log.print_ok_arrow(f"Downloaded {len(self.new_inventory)} items")
            shutil.copy(csv_file.name, self.csv_file)

        self._write_inventory_delta_file()
        self.last_inventory_update_time = now

        now_datetime = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)

        def generate_new_items():
            for item in self.new_inventory.itertuples(index=False):
                try:
                    is_new = skip_db_add or self._update_local_db_item("", item, now_datetime)
                    if not is_new:
                        continue
                except IntegrityError as e:
                    log.print_fail(f"IntegrityError: {e}")
                    continue

                inventory_available = int(item.total_available)
                nc_code = getattr(item, self.INVENTORY_CODE_KEY)
                brand_name = item.brand_name
                yield (nc_code, brand_name, inventory_available)

        new_items = list(generate_new_items())

        log.print_bold(f"Found {len(new_items) if new_items else 0} new items")
        return new_items

    def _update_sms_time_window(self, name: str) -> None:
        with ClientDb.client(name) as db:
            if db is None:
                return
            if (
                db.alert_time_range_end
                and db.alert_time_range_start
                and db.alert_time_zone
                and self.twilio_util
            ):
                for phone_number in db.phone_numbers:
                    self.twilio_util.update_send_window(
                        phone_number.number,
                        db.alert_time_range_start,
                        db.alert_time_range_end,
                        db.alert_time_zone,
                    )
            elif self.verbose:
                log.print_bright(f"Client {name} does not have a time window set")

    def _check_inventory(self, new_items: T.List[T.Tuple[str, str, int]]) -> None:
        self._update_cache_from_local_db()

        if not self.clients:
            log.print_fail("No clients to check inventory for")
            self.firebase_client.update_watchers()
            self.last_query_firebase_time = time.time()
            return

        for name, client in self.clients.items():
            log.print_bold(f"{'─' * 80}")
            log.print_bold(f"Checking inventory for {name}...")
            self._update_sms_time_window(name)
            log.print_bold(f"Checking monitored inventory")
            self.check_client_inventory(client)
            log.print_ok_blue_arrow("...Done")
            log.print_bold(f"Checking untracked new inventory")
            self.check_client_untracked_new_inventory(client, new_items)
            log.print_ok_blue_arrow("...Done")

        log.print_bold(f"{'─' * 80}")

        for name, client in self.clients.items():
            self._update_sms_time_window(name)
            if self.twilio_util:
                for phone_number in client["phone_numbers"]:
                    self.twilio_util.check_sms_queue(phone_number["number"])

        self._check_and_see_if_firebase_should_be_updated()
        self.skip_alerts = False

    def run(self) -> None:
        if self.firebase_client:
            self.firebase_client.health_ping()

        new_items = self.update_inventory(self.download_url)

        self._check_inventory(new_items)

        wait.wait(self.WAIT_TIME)
