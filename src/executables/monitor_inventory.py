"""
Monitor the inventory of the store
"""

import argparse
import getpass
import os

import dotenv

from database.connect import init_database
from database.models.client import Client
from firebase.firebase_client import FirebaseClient
from inventory_monitor import InventoryMonitor
from util import log, wait
from util.email import Email, get_email_accounts_from_password
from util.security import decrypt_secret, ENCRYPT_PASSWORD_ENV_VAR
from util.twilio_util import TwilioUtil


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    log_dir = log.get_logging_dir("inventory_manager")

    parser.add_argument("--wait-time", default=60, type=int, help="Time to wait between runs")
    parser.add_argument("--log-dir", default=log_dir)
    parser.add_argument(
        "--log-level",
        type=str,
        help="Logging level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument("--use-local-db", action="store_true", help="Use local database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the script without actually sending SMS",
    )
    parser.add_argument("--force-update", action="store_true", help="Force update of database")

    parser.add_argument("--verbose", action="store_true", help="Print more information")

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_args()

    dotenv.load_dotenv(".env")

    log.setup_log(args.log_level, args.log_dir, "db_convert")

    init_database(args.log_dir, os.environ.get("DEFAULT_DB"), Client, args.force_update)

    twilio_util = TwilioUtil(
        my_number=os.environ.get("TWILIO_FROM_SMS_NUMBER"),
        auth_token=os.environ.get("TWILIO_AUTH_TOKEN"),
        sid=os.environ.get("TWILIO_ACCOUNT_SID"),
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    email_credentials = [
        {
            "user": os.environ.get("ADMIN_EMAIL", ""),
            "password": os.environ.get("ADMIN_EMAIL_PASSWORD", ""),
        }
    ]

    email_accounts = []
    encrypt_password = os.environ.get(ENCRYPT_PASSWORD_ENV_VAR)
    if not encrypt_password:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
    email_accounts = get_email_accounts_from_password(encrypt_password, email_credentials)

    credentials_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    firebase_client: FirebaseClient = FirebaseClient(credentials_file, client)

    monitor: InventoryMonitor = InventoryMonitor(
        download_url=os.environ.get("INVENTORY_DOWNLOAD_URL"),
        download_key=os.environ.get("INVENTORY_DOWNLOAD_KEY"),
        twilio_util=twilio_util,
        admin_email=email_accounts[0],
        log_dir=args.log_dir,
        use_local_db=args.use_local_db,
        dry_run=args.dry_run,
    )

    monitor.init()

    while True:
        monitor.run()
        if not args.use_local_db:
            firebase_client.run()
        wait.wait(args.wait_time)


if __name__ == "__main__":
    main()
