"""
This is a class called InventoryMonitor that is used to monitor the inventory of a
- Inventory is monitored from this [site](https://abc.nc.gov/StoresBoards/Stocks)
- Inventory is updated every 15 minutes
- Inventory can be exported to CSV vie the following endpoint:
        https://abc.nc.gov/StoresBoards/ExportData
- CSV contains drink items. Each item is identified by a six digit code.

This class monitors the inventory and creates alerts based on a mapping of clients
to drink items. Alerts will be determined by the heuristic of specified inventory
going from sold out (qty 0) to various non-zero values. In other words, when
inventory goes from out of stock to in stock for specified items.

The alert system is done using [Twilio](https://www.twilio.com/en-us/pricing) and
sends the text message alert to the associated client. The initial setup will be pay
as you go plan on Twilio, and should be fairly reasonable costwise
"""
import os
import tempfile
import time
import typing as T

from util import csv_logger, log, web2_client
from util.twilio_util import TwilioUtil
from types.types import Client, Item


class InventoryMonitor:
    TIME_BETWEEN_INVENTORY_CHECKS = 60 * 15  # 15 minutes

    def __init__(self, download_url: str, twilio_util: TwilioUtil) -> None:
        self.download_url = download_url
        self.twilio_util: TwilioUtil = twilio_util
        self.clients = clients
        self.inventory = None
        self.web = web2_client.Web2Client()
        self.last_inventory_update_time = None

    def _is_time_to_check_inventory(self) -> bool:
        if self.last_inventory_update_time is None:
            return True

        return time.time() - self.last_inventory_update_time > self.TIME_BETWEEN_INVENTORY_CHECKS

    def _get_inventory(self) -> None:
        try:
            csv_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
            with open(csv_file.name, "w") as f:
                f.write(self.web.url_download(self.download_url, csv_file.name))

            csv = csv_logger.CsvLogger(csv_file, header)
        except Exception as e:
            log.print_error(f"Error getting inventory: {e}")
        finally:
            os.path.remove(csv_file.name)

        self.inventory = csv.read()
        self.last_inventory_update_time = time.time()

    def _check_inventory(self) -> None:
        for client in self.clients:
            self._check_client_inventory(client)

    def _check_client_inventory(self, client: Client) -> None:
        for item in client.items:
            if self._did_item_go_from_out_of_stock_to_in_stock(item):
                self.twilio_util.send_text(
                    client.phone_number,
                    f"{item.item_name} is now in stock with {item.quantity} left",
                )

    def _did_item_go_from_out_of_stock_to_in_stock(self, item: Item) -> bool:
        if item.item_code not in self.inventory:
            return False
        if item.quantity == 0:
            return False
        if self.inventory[item.item_code] == 0:
            return True
        return False

    def run(self) -> None:
        if not self._is_time_to_check_inventory():
            return
        self._get_inventory()
        self._check_inventory()
