"""
Monitor the inventory of the store
"""

import argparse
import os
import dotenv

from database.connect import init_database
from database.models.client import Client
from inventory_monitor import InventoryMonitor
from util import log
from util.twilio_util import TwilioUtil


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    log_dir = log.get_logging_dir("inventory_manager")

    parser.add_argument("--wait-time", default=60, type=int, help="Time to wait between runs")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument("--use-local-db", action="store_true", help="Use local database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the script without actually sending SMS",
    )

    parser.add_argument("--verbose", action="store_true", help="Print more information")

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_args()

    dotenv.load_dotenv(".env")

    log.setup_log(args.log_level, args.log_dir, "db_convert")

    init_database(args.log_dir, os.getenv("DEFAULT_DB"), Client)

    twilio_util = TwilioUtil(
        my_number=os.getenv("TWILIO_FROM_SMS_NUMBER"),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        sid=os.getenv("TWILIO_ACCOUNT_SID"),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    monitor: InventoryMonitor = InventoryMonitor(
        download_url=os.getenv("INVENTORY_DOWNLOAD_URL"),
        twilio_util=twilio_util,
        use_local_db=args.use_local_db,
    )

    monitor.init()

    while True:
        monitor.run()
        wait(args.wait_time)


if __name__ == "__main__":
    main()
