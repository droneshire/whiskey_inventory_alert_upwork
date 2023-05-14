"""
Monitor the inventory of the store
"""

import argparse
import os
import typing as T

import dotenv
from rich.progress import track

from database.client import DEFAULT_DB, ClientDb
from database.connect import init_database
from database.models.client import Client
from firebase.defs import Actions
from inventory_monitor import InventoryMonitor
from util import log
from util.email import Email
from util.twilio_util import TwilioUtil


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    log_dir = log.get_logging_dir("inventory_manager")

    parser.add_argument("--wait-time", default=60, type=int, help="Time to wait between runs")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--force-update", action="store_true", help="Force update of database")

    parser.add_argument(
        "--client",
        type=str,
        help="Name of the client",
        required=True,
    )
    return parser.parse_args()


def get_credentials_file() -> str:
    credentials_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    exec_dir = os.path.dirname(os.path.realpath(__file__))
    db_dir = os.path.dirname(exec_dir)
    src_dir = os.path.dirname(db_dir)
    top_dir = os.path.dirname(src_dir)
    return os.path.join(top_dir, credentials_file)


def main() -> None:
    args: argparse.Namespace = parse_args()

    dotenv.load_dotenv(".env")

    log.setup_log("ERROR", args.log_dir, "db_convert")

    init_database(args.log_dir, DEFAULT_DB, Client, args.force_update)

    monitor: InventoryMonitor = InventoryMonitor(
        download_url=os.environ.get("INVENTORY_DOWNLOAD_URL", ""),
        download_key=os.environ.get("INVENTORY_DOWNLOAD_KEY", ""),
        twilio_util=None,
        admin_email=None,
        log_dir=args.log_dir,
        credentials_file=get_credentials_file(),
        use_local_db=False,
        dry_run=False,
        verbose=False,
    )

    monitor.init()
    inventory_df = monitor.update_inventory(os.environ.get("INVENTORY_DOWNLOAD_URL", ""))

    if inventory_df.empty:
        log.print_fail("No inventory to use!")
        return

    # read each line in the pandas dataframe and add it to the database
    db_data = {"inventory": {"items": {}}}
    for index, row in track(
        inventory_df.iterrows(), description="Inventory", total=len(inventory_df)
    ):
        nc_code = row[monitor.INVENTORY_CODE_KEY]
        db_data["inventory"]["items"][nc_code] = {
            "name": row["Brand Name"],
            "available": row["Total Available"],
            "action": Actions.TRACKING.value,
        }
    monitor.firebase_client.add_items_to_firebase(args.client, db_data)


if __name__ == "__main__":
    main()
