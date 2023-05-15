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
from util import email, log
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
        log.print_normal(f"Sending SMS to {to_number} with content:\n{content}")
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
    temp_diff_file: T.Any = None
    test_client_name = "test"
    test_num = "+1234567890"

    def setUp(self) -> None:
        self.twilio_stub = TwilioUtilStub()

        self.email: email.Email = None

        dotenv.load_dotenv(".env")

        init_database(self.test_dir, DEFAULT_DB, Client, True)

        self.before_csv = os.path.join(self.test_dir, "inventory_before.csv")
        self.after_csv = os.path.join(self.test_dir, "inventory_after.csv")
        self.after_csv_many = os.path.join(self.test_dir, "inventory_after_many_change.csv")

        assert os.path.isfile(self.before_csv), f"Could not find {self.before_csv}"
        assert os.path.isfile(self.after_csv), f"Could not find {self.after_csv}"
        assert os.path.isfile(self.after_csv_many), f"Could not find {self.after_csv_many}"

        self.temp_csv_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_diff_file = tempfile.NamedTemporaryFile(delete=False)
        shutil.copyfile(self.before_csv, self.temp_csv_file.name)

        self.monitor = InventoryMonitor(
            download_url="",
            download_key="",
            twilio_util=self.twilio_stub,
            admin_email=self.email,
            inventory_csv_file=self.temp_csv_file.name,
            inventory_diff_file=self.temp_diff_file.name,
            time_between_inventory_checks=5,
            use_local_db=True,
            log_dir=self.test_dir,
            credentials_file="",
            dry_run=False,
            verbose=False,
        )

        self.monitor.init()

    def tearDown(self) -> None:
        dotenv.load_dotenv(".env")

        if self.temp_csv_file and os.path.isfile(self.temp_csv_file.name):
            os.remove(self.temp_csv_file.name)

        if self.temp_diff_file and os.path.isfile(self.temp_diff_file.name):
            os.remove(self.temp_diff_file.name)

        close_database()
        remove_database(self.test_dir, DEFAULT_DB)

        self.monitor = None
        self.twilio_stub = None

    def _setup_client(
        self, nc_codes: T.List[str], alert_range_enabled: bool, has_paid: bool, track: bool = True
    ) -> ClientSchema:
        ClientDb.add_client(self.test_client_name, "test@gmail.com", self.test_num)
        for nc_code in nc_codes:
            ClientDb.add_item_to_client_and_track(self.test_client_name, nc_code)

            if not track:
                ClientDb.add_track_item(self.test_client_name, nc_code, False)

        with ClientDb.client(self.test_client_name) as client:
            client.alert_range_enabled = alert_range_enabled
            client.has_paid = has_paid
            client_schema = ClientSchema().dump(client)

        return client_schema

    def test_out_of_stock_to_in_stock(self):
        client_schema = self._setup_client(["00009"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

    def test_no_send_if_no_previous_inventory_file(self):
        client_schema = self._setup_client(["00009"], True, True)

        # simulate no inventory file existing
        self.monitor.skip_alerts = True

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

    def test_change_above_threshold_that_was_in_inventory_before_doesnt_send(self):
        client_schema = self._setup_client(["00221"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

    def test_major_drop_in_inventory_doesnt_trigger_send(self):
        # items that all have non-zero inventory
        items_to_track = [
            "00018",
            "00127",
            "00139",
            "00221",
        ]
        client_schema = self._setup_client(items_to_track, True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        # create a temp file and copy the before csv into it except for half of the items
        temp_before_csv = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".csv")
        with open(self.before_csv, "r") as infile, open(temp_before_csv.name, "w") as outfile:
            lines = [l for i, l in enumerate(infile.readlines()) if i % 2 == 0]
            outfile.writelines(lines)

        self.monitor.update_inventory(temp_before_csv.name)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

    def test_unlisted_to_in_stock(self):
        client_schema = self._setup_client(["00120"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

        with ClientDb.client(self.test_client_name) as client:
            updates_sent = client.updates_sent
        self.assertEqual(updates_sent, 1)

    def test_listed_to_unlisted_has_zero_inventory(self):
        nc_code = "00139"
        client_schema = self._setup_client([nc_code], False, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        with ClientDb.item(nc_code) as item:
            item_available = item.total_available
        self.assertEqual(item_available, 190)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        with ClientDb.item(nc_code) as item:
            item_available = item.total_available
        self.assertEqual(item_available, 0)

    def test_many_come_into_stock(self):
        nc_codes = ["00107", "00111", "00120", "00127"]
        client_schema = self._setup_client(nc_codes, True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv_many)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

        with ClientDb.client(self.test_client_name) as client:
            updates_sent = client.updates_sent

        self.assertEqual(updates_sent, 4)

    def test_inventory_update_time(self):
        self.assertTrue(self.monitor._is_time_to_check_inventory())

    def test_new_and_last_inventory_check(self):
        client_schema = self._setup_client(["00120"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertTrue(self.monitor.new_inventory.equals(self.monitor.last_inventory))

    def test_no_tracking_items_are_not_sent(self):
        self._setup_client(["00009"], True, True, False)
        client_schema = self._setup_client(["00111"], True, True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)

    def test_send_window(self):
        client_schema = self._setup_client(["00009"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        now = datetime.datetime(2020, 1, 1, 12, 0, 0)

        # force the time to be outside the window
        start_time = 8 * 60
        end_time = 22 * 60
        timezone = "America/Los_Angeles"
        self.twilio_stub.update_send_window(self.test_num, start_time, end_time, timezone)

        self.twilio_stub.now = now

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)
        self.assertEqual(len(self.twilio_stub.message_queue[self.test_num]), 1)

        self.twilio_stub.now = datetime.datetime(2020, 1, 1, 12 + 8, 0, 0)
        self.twilio_stub.check_sms_queue(self.test_num, self.twilio_stub.now)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue[self.test_num]), 0)

    def test_ignore_send_window(self):
        client_schema = self._setup_client(["00009"], False, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        now = datetime.datetime(2020, 1, 1, 12, 0, 0)

        # force the time to be outside the window
        start_time = 8 * 60
        end_time = 22 * 60
        timezone = "America/Los_Angeles"
        self.twilio_stub.update_send_window(self.test_num, start_time, end_time, timezone)

        self.twilio_stub.now = now

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue[self.test_num]), 0)

        self.twilio_stub.now = datetime.datetime(2020, 1, 1, 12 + 8, 0, 0)
        self.twilio_stub.check_sms_queue(self.test_num, self.twilio_stub.now)

        self.assertEqual(self.twilio_stub.num_sent, 1)
        self.assertEqual(len(self.twilio_stub.message_queue[self.test_num]), 0)

    def test_client_not_paid_does_not_sent(self):
        client_schema = self._setup_client(["00009"], True, False)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.after_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

    def test_empty_csv_does_not_send(self):
        client_schema = self._setup_client(["00009"], True, True)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        # create an "empty" csv file, just the header
        temp_csv = tempfile.NamedTemporaryFile(mode="w", delete=False)
        try:
            with open(self.before_csv, "r") as infile, open(temp_csv.name, "w") as outfile:
                for line in infile.readlines():
                    outfile.write(line)
                    break

            self.monitor.update_inventory(temp_csv.name)
        finally:
            os.remove(temp_csv.name)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)

        self.monitor.update_inventory(self.before_csv)
        self.monitor.check_client_inventory(client_schema)

        self.assertEqual(self.twilio_stub.num_sent, 0)


if __name__ == "__main__":
    unittest.main()
