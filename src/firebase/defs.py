import datetime
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
    inventory_change: int
    min_hours_since_out_of_stock: int


class Email(T.TypedDict):
    email: str
    updatesEnabled: bool


class TimeZone(T.TypedDict):
    abbrev: str
    altName: str
    label: str
    offset: int
    value: str


class Sms(T.TypedDict):
    phoneNumber: str
    updatesEnabled: bool
    alertWindowEnabled: bool
    alertTimeRange: T.List[str]
    alertTimeZone: TimeZone


class Notifications(T.TypedDict):
    email: Email
    sms: Sms


class Preferences(T.TypedDict):
    notifications: Notifications


class Accounting(T.TypedDict):
    plan: str
    nextBillingDate: str
    nextBillingAmount: float
    hasPaid: bool


class Client(T.TypedDict):
    inventory: Inventory
    preferences: Preferences
    accounting: Accounting


NULL_CLIENT = Client(
    accounting=Accounting(
        plan="",
        nextBillingDate="",
        nextBillingAmount=0.0,
        hasPaid=False,
    ),
    inventory=Inventory(items=[], inventory_change=1, min_hours_since_out_of_stock=0),
    preferences=Preferences(
        notifications=Notifications(
            email=Email(email="", updatesEnabled=False),
            sms=Sms(
                phoneNumber="",
                updatesEnabled=False,
                alertWindowEnabled=True,
                alertTimeRange=[],
                alertTimeZone=TimeZone(
                    abbrev="PDT",
                    altName="Pacific Daylight Time",
                    label="(GMT-07:00) Pacific Time",
                    offset=-7,
                    value="America/Los_Angeles",
                ),
            ),
        )
    ),
)
