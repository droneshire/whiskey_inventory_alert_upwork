import os
import tempfile
import time

import pandas as pd
import typing as T

from database.models.client import Client, ClientSchema
from database.models.item import Item, ItemSchema
from util import csv_log, log, web2_client, wait
from util.twilio_util import TwilioUtil


class InventoryMonitor:
    TIME_BETWEEN_INVENTORY_CHECKS = 60 * 15  # 15 minutes
    WAIT_TIME = 60
    INVENTORY_CODE_KEY = "NC Code"

    def __init__(
        self,
        download_url: str,
        twilio_util: TwilioUtil,
        time_between_inventory_checks: int = None,
    ) -> None:
        self.download_url = download_url
        self.twilio_util: TwilioUtil = twilio_util
        self.time_between_inventory_checks = (
            time_between_inventory_checks | self.TIME_BETWEEN_INVENTORY_CHECKS
        )

        self.clients = []

        self.last_inventory = pd.core.frame.DataFrame | None
        self.new_inventory = pd.core.frame.DataFrame | None

        self.web = web2_client.Web2Client()

        self.last_inventory_update_time = None

    def init(self) -> None:
        self.clients = Client.query.all()

    def _is_time_to_check_inventory(self) -> bool:
        if self.last_inventory_update_time is None:
            return True

        return time.time() - self.last_inventory_update_time > self.time_between_inventory_checks

    def _check_client_inventory(client: Client) -> None:
        if client is None:
            return

        for item in client.items:
            if self._did_item_go_from_out_of_stock_to_in_stock(item):
                message = f"{item.nc_code}: {item.brand_name} is now in stock with {item.total_available} left"
                self.twilio_util.send_sms(
                    client.phone_number,
                    message,
                )
                log.print_ok_arrow(message)

    def _get_item_from_inventory(
        self, item: Item, dataframe: pd.core.frame.DataFrame
    ) -> T.List[T.Any]:
        inventory_codes = dataframe[self.INVENTORY_CODE_KEY]

        inventory_matches = dataframe[dataframe[self.INVENTORY_CODE_KEY] == item.nc_code]

        if len(inventory_matches) == 0:
            return []

        return inventory_matches.iloc[0]

    def _did_item_go_from_out_of_stock_to_in_stock(self, item: Item) -> bool:
        inventory_codes = self.new_inventory[self.INVENTORY_CODE_KEY]

        log.print_normal(f"Checking {item.nc_code}:{item.brand_name} for inventory...")

        if item.nc_code not in inventory_codes:
            return False
        if item.total_available == 0:
            return False
        if len(inventory_matches) == 0:
            return False

        old_inventory_codes = self.new_inventory[self.INVENTORY_CODE_KEY]

        return False

    def _update_inventory(self) -> None:
        try:
            csv_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
            self.web.url_download(self.download_url, csv_file.name)
            inventory_pd: pd.core.frame.DataFrame = pd.read_csv(csv_file.name)
        except Exception as e:
            log.print_error(f"Error getting inventory: {e}")
            return
        finally:
            os.path.remove(csv_file.name)

        # clean up the code column
        inventory_pd[self.INVENTORY_CODE_KEY] = inventory_pd[self.INVENTORY_CODE_KEY].str.replace(
            '="', "", regex=False
        )

        self.last_inventory_update_time = time.time()
        self.new_inventory = inventory_pd

    def _check_inventory(self) -> None:
        if not self.clients:
            return

        self._update_inventory()

        for client in self.clients:
            self._check_client_inventory(client, old_inventory, new_inventory)

    def run(self) -> None:
        if not self._is_time_to_check_inventory():
            return

        self._check_inventory()
