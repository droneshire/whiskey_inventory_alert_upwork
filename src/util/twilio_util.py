import datetime
import time
import typing as T

import pytz
from twilio.rest import Client

from util import log


class TwilioUtil:
    def __init__(
        self,
        my_number: str,
        auth_token: str,
        sid: str,
        dry_run=False,
        verbose=False,
        time_between_sms: int = 1,
        ignore_time_window: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.verbose = verbose

        self.sms_client = Client(sid, auth_token) if auth_token else None
        self.my_number = my_number

        if dry_run:
            log.print_warn("TwilioUtil in dry run mode...")

        if verbose:
            log.print_bold("TwilioUtil initialized")

        self.message_queue: T.List[str] = []
        self.start_time_minutes: int = 9 * 60 + 30
        self.end_time_minutes: int = 17 * 60 + 30
        self.timezone: T.Any = pytz.timezone("America/Los_Angeles")
        self.time_between_sms: int = time_between_sms
        self.ignore_time_window: bool = ignore_time_window

    def _get_minutes_from_time(self, time: datetime.datetime) -> int:
        return time.hour * 60 + time.minute

    def update_send_window(
        self, start_time: datetime.datetime, end_time: datetime.datetime, timezone: str
    ) -> None:
        self.start_time_minutes = self._get_minutes_from_time(start_time)
        self.end_time_minutes = self._get_minutes_from_time(end_time)
        self.timezone = pytz.timezone(timezone)
        log.print_bright(
            "Updated send window to: {} - {} ({})",
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            timezone,
        )

    def send_sms_if_in_window(
        self, to_number: str, content: str, now: datetime.datetime = datetime.datetime.now()
    ) -> None:
        self.message_queue.append((to_number, content))
        if self.verbose:
            log.print_normal(f"Added SMS to queue: {to_number} - {content}")
        self.check_sms_queue(now)

    def send_sms(self, to_number: str, content: str) -> None:
        if self.dry_run:
            return

        message = self.sms_client.messages.create(
            body=content,
            from_=self.my_number,
            to=to_number,
        )

        if self.verbose:
            log.print_bold(f"Sent SMS: {message.sid} - {content}")

    def check_sms_queue(self, now: datetime.datetime = datetime.datetime.now()) -> None:
        now.replace(tzinfo=pytz.utc).astimezone(tz=self.timezone)
        now_minutes = self._get_minutes_from_time(now)

        is_within_window = (
            now_minutes >= self.start_time_minutes and now_minutes <= self.end_time_minutes
        )

        if is_within_window or self.ignore_time_window:
            for message in self.message_queue:
                self.send_sms(message[0], message[1])
                time.sleep(self.time_between_sms)
            self.message_queue = []
        else:
            log.print_ok_blue_arrow("Not in send window, not sending SMS")
