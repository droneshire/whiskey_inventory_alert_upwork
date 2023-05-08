import datetime
import os
import shutil
import tempfile
import time
import typing as T
import unittest

import dotenv

from database.client import DEFAULT_DB, ClientDb
from database.connect import close_database, init_database, remove_database
from database.models.client import Client, ClientSchema
from database.models.item import ItemSchema
from inventory_monitor import InventoryMonitor
from util import log
from util.twilio_util import TwilioUtil


class TwilioUtilStub(TwilioUtil):
    def __init__(self):
        super().__init__("", "", "", verbose=True, time_between_sms=0)
        self.num_sent = 0
        self.send_to = ""
        self.content = ""
        self.now: datetime.datetime = datetime.datetime(2021, 1, 1, 12 + 8, 0, 0)

    def send_sms_if_in_window(
        self, to_number: str, content: str, now: datetime.datetime = datetime.datetime.utcnow()
    ) -> None:
        super().send_sms_if_in_window(to_number, content, self.now)

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
    after_csv_many: str = ""
    twilio_stub: TwilioUtilStub = None
    test_dir: str = os.path.join(os.path.dirname(__file__), "test_data")
    temp_csv_file: T.Any = None

    def setUp(self) -> None:
        self.twilio_stub = TwilioUtilStub()

        dotenv.load_dotenv(".env")

        init_database(self.test_dir, DEFAULT_DB, Client, True)

        self.before_csv = os.path.join(self.test_dir, "inventory_before.csv")
        self.after_csv = os.path.join(self.test_dir, "inventory_after.csv")
        self.after_csv_many = os.path.join(self.test_dir, "inventory_after_many_change.csv")

        assert os.path.isfile(self.before_csv), f"Could not find {self.before_csv}"
        assert os.path.isfile(self.after_csv), f"Could not find {self.after_csv}"
        assert os.path.isfile(self.after_csv_many), f"Could not find {self.after_csv_many}"

        self.temp_csv_file = tempfile.NamedTemporaryFile(delete=False)
        shutil.copyfile(self.before_csv, self.temp_csv_file.name)

        self.monitor = InventoryMonitor(
            download_url="",
            download_key="",
            twilio_util=self.twilio_stub,
            admin_email=None,
            inventory_csv_file=self.temp_csv_file.name,
            time_between_inventory_checks=5,
            use_local_db=True,
            log_dir=self.test_dir,
            credentials_file="",
            dry_run=False,
        )

        self.monitor.init()

    def tearDown(self) -> None:
        dotenv.load_dotenv(".env")

        if self.temp_csv_file and os.path.isfile(self.temp_csv_file.name):
            os.remove(self.temp_csv_file.name)

        close_database()
        remove_database(self.test_dir, DEFAULT_DB)

        self.monitor = None
        self.twilio_stub = None

    def test_out_of_stock_to_in_stock(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00009")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

    def test_unlisted_to_in_stock(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00120")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

        with ClientDb.client(test_client_name) as client:
            updates_sent = client.updates_sent
        self.assertEqual(updates_sent, 1)

    def test_many_come_into_stock(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00107")
        ClientDb.add_item_to_client_and_track(test_client_name, "00111")
        ClientDb.add_item_to_client_and_track(test_client_name, "00120")
        ClientDb.add_item_to_client_and_track(test_client_name, "00127")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        df = self.monitor.update_inventory(self.after_csv_many)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

        with ClientDb.client(test_client_name) as client:
            updates_sent = client.updates_sent

        self.assertEqual(updates_sent, 4)

    def test_inventory_update_time(self):
        self.assertTrue(self.monitor._is_time_to_check_inventory())

    def test_new_and_last_inventory_check(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00120")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertTrue(self.monitor.new_inventory.equals(self.monitor.last_inventory))

    def test_no_tracking_items_are_not_sent(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        nc_code = "00009"
        ClientDb.add_item_to_client_and_track(test_client_name, nc_code)
        ClientDb.add_track_item(test_client_name, nc_code, False)

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

    def test_send_window(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00009")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        now = datetime.datetime(2020, 1, 1, 12, 0, 0)

        # force the time to be outside the window
        start_time = 8 * 60
        end_time = 22 * 60
        timezone = "America/Los_Angeles"
        self.twilio_stub.update_send_window(start_time, end_time, timezone)

        self.twilio_stub.now = now

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)
        self.assertEqual(len(self.twilio_stub.message_queue), 1)

        self.twilio_stub.now = datetime.datetime(2020, 1, 1, 12 + 8, 0, 0)
        self.twilio_stub.check_sms_queue(self.twilio_stub.now)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue), 0)

    def test_ignore_send_window(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        ClientDb.add_item_to_client_and_track(test_client_name, "00009")

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = False
            client.has_paid = True
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        now = datetime.datetime(2020, 1, 1, 12, 0, 0)

        # force the time to be outside the window
        start_time = 8 * 60
        end_time = 22 * 60
        timezone = "America/Los_Angeles"
        self.twilio_stub.update_send_window(start_time, end_time, timezone)

        self.twilio_stub.now = now

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue), 0)

        self.twilio_stub.now = datetime.datetime(2020, 1, 1, 12 + 8, 0, 0)
        self.twilio_stub.check_sms_queue(self.twilio_stub.now)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue), 0)

    def test_client_not_paid_does_not_sent(self):
        test_client_name = "test"

        ClientDb.add_client(test_client_name, "test@gmail.com", "+1234567890")
        nc_code = "00009"
        ClientDb.add_item_to_client_and_track(test_client_name, nc_code)
        ClientDb.add_track_item(test_client_name, nc_code, False)

        with ClientDb.client(test_client_name) as client:
            client.alert_range_enabled = True
            client.has_paid = False
            client_schema = ClientSchema().dump(client)

        df = self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        df = self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)


if __name__ == "__main__":
    unittest.main()
