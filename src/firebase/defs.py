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


class Email(T.TypedDict):
    email: str
    updatesEnabled: bool


class Sms(T.TypedDict):
    phoneNumber: str
    updatesEnabled: bool


class TimeZone(T.TypedDict):
    abbrev: str
    altName: str
    label: str
    offset: int
    value: str


class Notifications(T.TypedDict):
    email: Email
    sms: Sms
    alertTimeRange: T.List[datetime.datetime]
    alertTimeZone: TimeZone


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
            alertTimeRange=[],
            alertTimeZone=TimeZone(
                abbrev="PDT",
                altName="Pacific Daylight Time",
                label="(GMT-07:00) Pacific Time",
                offset=-7,
                value="America/Los_Angeles",
            ),
        )
    ),
)
