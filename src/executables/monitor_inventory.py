"""
Monitor the inventory of the store
"""

import argparse
import getpass
import os
import typing as T

import dotenv

from database.connect import init_database
from database.models.client import Client
from inventory_monitor import InventoryMonitor
from util import log, wait
from util.email import Email, get_email_accounts_from_password
from util.security import ENCRYPT_PASSWORD_ENV_VAR, decrypt_secret
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


def get_email_accounts() -> T.List[Email]:
    """
    We support multiple email accounts b/c we can be send rate limited
    by gmail if we send too many emails from one account

    We store the encrypted password in our environment, but we encrypt it
    with an entered key so that we don't have to store the password in plaintext
    """
    email_credentials = [
        {
            "user": os.environ.get("ADMIN_EMAIL", ""),
            "password": os.environ.get("ADMIN_EMAIL_PASSWORD_ENCRYPTED", ""),
        }
    ]

    email_accounts = []
    encrypt_password = os.environ.get(ENCRYPT_PASSWORD_ENV_VAR)
    if not encrypt_password:
        encrypt_password = getpass.getpass(prompt="Enter decryption password: ")
    email_accounts = get_email_accounts_from_password(encrypt_password, email_credentials)

    return email_accounts


def get_credentials_file() -> str:
    credentials_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    exec_dir = os.path.dirname(os.path.realpath(__file__))
    src_dir = os.path.dirname(exec_dir)
    top_dir = os.path.dirname(src_dir)
    return os.path.join(top_dir, credentials_file)


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

    email_accounts = get_email_accounts()

    monitor: InventoryMonitor = InventoryMonitor(
        download_url=os.environ.get("INVENTORY_DOWNLOAD_URL"),
        download_key=os.environ.get("INVENTORY_DOWNLOAD_KEY"),
        twilio_util=twilio_util,
        admin_email=email_accounts[0],
        log_dir=args.log_dir,
        credentials_file=get_credentials_file(),
        use_local_db=args.use_local_db,
        dry_run=args.dry_run,
    )

    monitor.init()

    while True:
        monitor.run()
        wait.wait(args.wait_time)


if __name__ == "__main__":
    main()
