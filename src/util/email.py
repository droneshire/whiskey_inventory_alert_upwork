import typing as T

import yagmail

from util import log
from util.security import decrypt_secret


class Email(T.TypedDict):
    address: str
    password: str
    quiet: bool


def get_email_accounts_from_password(
    encrypt_password: str,
    encrypted_emails: T.List[T.Dict[str, str]],
    dry_run: bool = False,
) -> T.List[Email]:
    email_accounts = []
    for email_account in encrypted_emails:
        email_password = decrypt_secret(encrypt_password, email_account["password"])
        email_accounts.append(
            Email(
                address=email_account["user"],
                password=email_password,
                quiet=dry_run,
            )
        )
    return email_accounts


def send_email_raw(
    email: Email,
    to_addresses: T.List[str],
    subject: str,
    content: str,
    attachments: T.List[str] = None,
    verbose: bool = False,
) -> None:
    with yagmail.SMTP(email["address"], email["password"]) as email_sender:
        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]
            email_sender.send(
                to=to_addresses,
                subject=subject,
                contents=content,
                attachments=attachments,
            )
        if verbose:
            log.print_ok(f"To: {', '.join(to_addresses)}\nFrom: {email['address']}")
            log.print_ok(f"Subject: {subject}")
            log.print_ok(f"{content}")


def send_email(
    emails: T.List[Email],
    to_addresses: T.List[str],
    subject: str,
    content: str,
    attachments: T.List[str] = None,
    verbose: bool = False,
) -> None:
    for email in emails:
        if email["quiet"]:
            continue
        try:
            send_email_raw(
                email,
                to_addresses,
                subject,
                content,
                attachments=attachments,
                verbose=verbose,
            )
            return
        except KeyboardInterrupt:
            raise
        except:
            pass

    log.print_fail("Failed to send email alert")
