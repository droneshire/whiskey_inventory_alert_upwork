import types
import typing as T


class Item(T.SimpleNamespace):
    item_code: str
    item_name: str
    quantity: int


class Client(T.SimpleNamespace):
    phone_number: str
    items: T.List[Item]
