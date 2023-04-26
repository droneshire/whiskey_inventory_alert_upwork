# set up google python test framework
import os
import time
import typing as T
import unittest

import dotenv
import pandas as pd

from database.connect import init_database
from database.models.client import Client, ClientSchema
from database.models.item import ItemSchema
from inventory_monitor import InventoryMonitor
from util import log
from util.twilio_util import TwilioUtil


class TwilioUtilStub(TwilioUtil):
    def __init__(self):
        super().__init__("", "", "")
        self.did_send = False
        self.send_to = ""
        self.content = ""

    def send_sms(self, to_number, content) -> None:
        self.did_send = True
        self.send_to = to_number
        self.content = content
        return


class InventoryManagementTest(unittest.TestCase):
    monitor: InventoryMonitor = None
    before_csv: str = ""
    after_csv: str = ""
    twilio_stub: TwilioUtilStub = None

    def setUp(self, interval: int = 5) -> InventoryMonitor:
        self.twilio_stub = TwilioUtilStub()

        dotenv.load_dotenv()

        test_dir = os.path.join(os.path.dirname(__file__), "test_data")

        init_database(test_dir, os.getenv("DEFAULT_DB"), Client, False)

        self.before_csv = os.path.join(test_dir, "inventory_before.csv")
        self.after_csv = os.path.join(test_dir, "inventory_after.csv")

        self.monitor = InventoryMonitor(
            download_url="",
            client_db=client_db,
            twilio_util=self.twilio_stub,
            time_between_inventory_checks=interval,
            verbose=True,
        )

        monitor.init()

    # have it test the inventory monitor using the test data in the test_data folder
    def test_sms_alert(self):
        items = [ItemSchema().load({"id": 1, "client_id": 1, "nc_code": "00009"})]
        client = ClientSchema().load(
            {
                "id": 1,
                "name": "test",
                "phone_number": "+1234567890",
                "email": "test@gmail.com",
                "items": items,
            }
        )

        self.monitor.update_inventory(self.before_csv)
        did_send = self.monitor.check_client_inventory(client)

        self.assertEqual(did_send, False)
        self.assertEqual(self.twilio_stub.did_send, False)

        self.monitor.update_inventory(self.after_csv)
        did_send = self.monitor.check_client_inventory(client)

        self.assertEqual(did_send, True)
        self.assertEqual(self.twilio_stub.did_send, True)

    def test_inventory_update_time(self):
        self.assertTrue(self.monitor._is_time_to_check_inventory())


if __name__ == "__main__":
    unittest.main()
