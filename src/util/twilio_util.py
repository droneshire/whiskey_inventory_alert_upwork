from twilio.rest import Client

from util import log


class TwilioUtil:
    def __init__(
        self, my_number: str, auth_token: str, sid: str, dry_run=False, verbose=False
    ) -> None:
        self.dry_run = dry_run
        self.verbose = verbose

        self.sms_client = Client(sid, auth_token) if auth_token else None
        self.my_number = my_number

        if dry_run:
            log.print_warn("TwilioUtil in dry run mode...")

        if verbose:
            log.print_bold("TwilioUtil initialized")

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
