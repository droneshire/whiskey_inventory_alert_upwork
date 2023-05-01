import enum
import typing as T


class Actions(enum.Enum):
    TRACKING = "TRACKING"
    NOT_TRACKING = "UNTRACKED"


class Items(T.TypedDict):
    name: str
    action: str
    inventory: int


class Inventory(T.TypedDict):
    items: T.List[Items]


class Email(T.TypedDict):
    email: str
    updatesEnabled: bool


class Sms(T.TypedDict):
    phoneNumber: str
    updatesEnabled: bool


class Notifications(T.TypedDict):
    email: Email
    sms: Sms


class Preferences(T.TypedDict):
    notifications: Notifications


class Client(T.TypedDict):
    inventory: Inventory
    preferences: Preferences


NULL_CLIENT = Client(
    inventory=Inventory(items=[]),
    preferences=Preferences(
        notifications=Notifications(
            email=Email(email="", updatesEnabled=False),
            sms=Sms(phoneNumber="", updatesEnabled=False),
        )
    ),
)
