import argparse
import os
import typing as T

import dotenv

from database.connect import init_database
from database.helpers import add_client, add_item
from database.models.client import Client
from util import log


class TestClient(T.NamedTuple):
    name: str
    email: str
    phone_number: str


dotenv.load_dotenv(".env")

TEST_CLIENT = TestClient(
    os.getenv("TEST_CLIENT_NAME"),
    os.getenv("TEST_CLIENT_EMAIL"),
    os.getenv("TEST_CLIENT_PHONE"),
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    log_dir = log.get_logging_dir("inventory_manager")

    parser.add_argument("--log-dir", default=log_dir)

    # item nc_code argument
    parser.add_argument(
        "--name",
        type=str,
        help="Name of the client",
        default=TEST_CLIENT.name,
    )

    parser.add_argument(
        "--email",
        type=str,
        help="Email of the client",
        default=TEST_CLIENT.email,
    )

    parser.add_argument(
        "--phone-number",
        type=str,
        help="Phone number of the client",
        default=TEST_CLIENT.phone_number,
    )

    parser.add_argument("--item-code", type=str, help="Item code of the item to add")

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_args()

    dotenv.load_dotenv(".env")

    init_database(args.log_dir, os.getenv("DEFAULT_DB"), Client)

    add_client(args.name, args.email, args.phone_number)

    if args.item_code:
        add_item(args.name, args.item_code)


if __name__ == "__main__":
    main()
