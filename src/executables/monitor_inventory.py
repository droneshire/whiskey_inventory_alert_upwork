"""
Monitor the inventory of the store
"""

import argparse
import dotenv

from inventory_monitor import InventoryMonitor
from util.twilio_util import TwilioUtil


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the script without actually sending SMS",
    )

    parser.add_argument("--verbose", action="store_true", help="Print more information")

    return parser.parse_args()


def main():
    args = parse_args()

    dotenv.load_dotenv(".env")

    twilio_util = TwilioUtil(
        my_number=os.getenv("TWILIO_FROM_SMS_NUMBER"),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        sid=os.getenv("TWILIO_ACCOUNT_SID"),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    monitor: InventoryMonitor = InventoryMonitor(
        download_url=os.getenv("INVENTORY_DOWNLOAD_URL"), twilio_util=twilio_util
    )


if __name__ == "__main__":
    main()
