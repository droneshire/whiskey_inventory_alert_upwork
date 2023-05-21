import os

import dotenv

from youngsville_inventory import YoungsvilleAbcInventory


def main() -> None:
    dotenv.load_dotenv(".env")

    password = os.getenv("YOUNGSVILLE_ABC_PASSWORD")
    username = os.getenv("YOUNGSVILLE_ABC_USERNAME")

    inventory = YoungsvilleAbcInventory(username, password)

    inventory.login()
    df = inventory.inventory_to_dataframe()
    print(df)


if __name__ == "__main__":
    main()
