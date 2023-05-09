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
    ) -> None:
        self.dry_run = dry_run
        self.verbose = verbose

        self.sms_client = Client(sid, auth_token) if auth_token else None
        self.my_number = my_number

        if dry_run:
            log.print_warn("TwilioUtil in dry run mode...")

        if verbose:
            log.print_bold("TwilioUtil initialized")

        self.message_queue: T.Dict[str, T.List[str]] = {}
        self.window: T.Dict[str, T.Dict[str, T.Any]] = {}
        self.ignore_time_window: T.Dict[str, bool] = {}

        self.time_between_sms: int = time_between_sms

    def _get_minutes_from_time(self, time: datetime.datetime) -> int:
        return time.hour * 60 + time.minute

    def set_ignore_time_window(self, to_number: str, ignore: bool) -> None:
        if to_number in self.ignore_time_window and self.ignore_time_window[to_number] != ignore:
            log.print_bright("Setting ignore_time_window to {}", ignore)
        self.ignore_time_window[to_number] = ignore

    def update_send_window(
        self, to_number: str, start_time: int, end_time: int, timezone: str
    ) -> None:
        log.print_bright(
            f"Updating {timezone} send window to: {start_time // 60}:{start_time % 60:02} - {end_time // 60}:{end_time % 60:02} ({timezone})"
        )
        self.window[to_number] = {
            "start_time": start_time,
            "end_time": end_time,
            "timezone": pytz.timezone(timezone),
        }

    def send_sms_if_in_window(
        self, to_number: str, content: str, now: datetime.datetime = datetime.datetime.utcnow()
    ) -> None:
        if to_number not in self.message_queue:
            self.message_queue[to_number] = []
        self.message_queue[to_number].append((to_number, content))
        log.print_normal(f"Added SMS to queue: {to_number} - {content}")
        self.check_sms_queue(to_number, now)

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

    def check_sms_queue(
        self, to_number: str, now: datetime.datetime = datetime.datetime.utcnow()
    ) -> None:
        if to_number in self.window:
            start_time = self.window[to_number].get("start_time", 60 * 60 * 8)
            end_time = self.window[to_number].get("end_time", 60 * 60 * 18)
            timezone = self.window[to_number].get("timezone", "America/Los_Angeles")

            log.print_normal(f"Time in UTC: {now.strftime('%H:%M:%S')}")
            now_with_tz = pytz.utc.localize(now)
            converted_to_tz = now_with_tz.astimezone(timezone)
            log.print_normal(f"Time in {timezone}: {converted_to_tz.strftime('%H:%M:%S')}")
            now_minutes = self._get_minutes_from_time(converted_to_tz)

            is_within_window = now_minutes >= start_time and now_minutes <= end_time
            should_send = is_within_window or self.ignore_time_window.get(to_number, True)

            if not should_send:
                log.print_ok_blue_arrow(
                    f"Not in send window "
                    f"({start_time // 60}:{start_time % 60:02}-"
                    f"{end_time // 60}:{end_time % 60:02}),"
                    f" currently {now_minutes // 60}:{now_minutes % 60:02} "
                    f"{timezone}. Not sending SMS"
                )
        else:
            should_send = True

        if should_send and to_number in self.message_queue:
            for message in self.message_queue[to_number]:
                self.send_sms(message[0], message[1])
                time.sleep(self.time_between_sms)
            self.message_queue[to_number] = []
