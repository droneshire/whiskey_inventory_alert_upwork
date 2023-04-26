# set up google python test framework
import os
import time
import typing as T
import unittest

import dotenv

from database.client import ClientDb
from database.connect import close_database, init_database
from database.models.client import Client, ClientSchema
from database.models.item import ItemSchema
from inventory_monitor import InventoryMonitor
from util import log
from util.twilio_util import TwilioUtil
from database.helpers import add_client, add_item


class TwilioUtilStub(TwilioUtil):
    def __init__(self):
        super().__init__("", "", "")
        self.num_sent = 0
        self.send_to = ""
        self.content = ""

    def send_sms(self, to_number: str, content: str) -> None:
        log.print_normal(f"Sending SMS to {to_number} with content {content}")
        self.num_sent += 1
        self.send_to = to_number
        self.content = content
        return

    def reset(self) -> None:
        self.num_sent = 0
        self.send_to = ""
        self.content = ""
        return


class InventoryManagementTest(unittest.TestCase):
    monitor: InventoryMonitor = None
    before_csv: str = ""
    after_csv: str = ""
    twilio_stub: TwilioUtilStub = None

    def setUp(self) -> InventoryMonitor:
        self.twilio_stub = TwilioUtilStub()

        dotenv.load_dotenv()

        test_dir = os.path.join(os.path.dirname(__file__), "test_data")

        init_database(test_dir, os.getenv("DEFAULT_DB"), Client, True)

        self.before_csv = os.path.join(test_dir, "inventory_before.csv")
        self.after_csv = os.path.join(test_dir, "inventory_after.csv")

        self.monitor = InventoryMonitor(
            download_url="",
            download_key="",
            twilio_util=self.twilio_stub,
            time_between_inventory_checks=5,
            use_local_db=True,
            log_dir=test_dir,
            dry_run=False,
        )

        self.monitor.init()

    def tearDown(self) -> None:
        close_database()
        self.monitor = None
        self.twilio_stub = None

    # have it test the inventory monitor using the test data in the test_data folder
    def test_sms_alert(self):
        test_client_name = "test"

        add_client(test_client_name, "test@gmail.com", "+1234567890")
        add_item(test_client_name, "00009")

        db = ClientDb(test_client_name)
        with db.client() as client:
            client_schema = ClientSchema().dump(client)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

    def test_inventory_update_time(self):
        self.assertTrue(self.monitor._is_time_to_check_inventory())


if __name__ == "__main__":
    unittest.main()
