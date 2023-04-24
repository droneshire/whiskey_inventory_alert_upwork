import argparse
import dotenv
import os
import typing as T

from database.client import ClientDb
from database import connect
from util import log


class TestClient(T.NamedTuple):
    name: str
    email: str
    phone_number: str


dotenv.load_dotenv(".env")

TEST_CLIENT = TestClient(
    os.getenv("TEST_CLIENT_NAME"),
    os.getenv("TEST_CLIENT_EMAIL"),
    os.getenv("TEST_CLIENT_PHONE_NUMBER"),
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    log_dir = log.get_logging_dir("inventory_manager")

    parser.add_argument("--log-dir", default=log_dir)

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_args()

    connect.init_database(args.log_dir, os.getenv("DEFAULT_DB"))

    client = ClientDb(TEST_CLIENT.name)

    client.add_client(TEST_CLIENT.name, TEST_CLIENT.email, TEST_CLIENT.phone_number)

    log.print_bold("Adding items")


if __name__ == "__main__":
    main()
