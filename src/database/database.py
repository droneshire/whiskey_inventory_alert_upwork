from __future__ import annotations

import time
import typing as T

from sqlalchemy.sql import func

from bots.database.account import Account
from bots.database.connect import ManagedSession
from util import log


class FollowBotDatabaseManager:
    DUMMY_ID = -1
    MIN_STARTING_ID = 353824990

    def update_account(self, imvu_id: int, last_follow: int, new_follows: int) -> None:
        with ManagedSession() as db:
            if db.query(Account).count() == 0:
                return None

            account = db.query(Account).filter(Account.imvu_id == imvu_id).first()

            if account is None:
                log.print_warn(f"Did not find {imvu_id} in the database")
                return None

            account.follow_time = func.now()
            account.last_follow = last_follow
            account.followings += new_follows

            try:
                db.add(account)
            except:
                log.print_fail(f"Failed to update database entry for {imvu_id}")

    def delete_user(self, username: str) -> None:
        with ManagedSession() as db:
            try:
                account = db.query(Account).filter(Account.email == username).first()
                if account is None or account.imvu_id == self.DUMMY_ID:
                    return
                log.print_normal(f"Deleting {username} from database...")
                db.query(Account).filter(Account.email == username).delete()
            except:
                log.print_fail(f"Failed to delete database entry for {username}")

    def insert_user(
        self,
        profile: T.Dict[T.Any, T.Any],
        email: str,
        password: str,
        last_follow: int | None = None,
    ) -> None:
        user_id = profile.get("legacy_cid", None)

        if user_id is None:
            log.print_warn(f"Invalid profile....")
            return

        account = None
        with ManagedSession() as db:
            account = db.query(Account).filter(Account.imvu_id == user_id).first()

        if account is not None:
            log.print_warn(f"{user_id} already in the database, not creating new user")
            return

        account = Account(
            imvu_id=user_id,
            country=profile.get("country", ""),
            adult=profile.get("is_adult", False),
            followings=0,
            email=email,
            password=password,
        )

        if last_follow is not None:
            account.last_follow = last_follow

        with ManagedSession() as db:
            if db.query(Account).filter(Account.imvu_id == user_id).count() > 0:
                log.print_warn(f"Already added in database...skipping add")
                return

            try:
                log.print_normal(f"Adding {user_id} to database...")
                db.add(account)
            except:
                log.print_fail(f"Failed to add db entry for {user_id}: {profile}")

    def get_latest_follow_id(self) -> int:
        with ManagedSession() as db:
            account = db.query(Account).filter(Account.imvu_id == self.DUMMY_ID).first()
            if account is None:
                account = db.query(Account, func.max(Account.last_follow)).first()
                if account:
                    last_follow = int(account.last_follow)
                else:
                    last_follow = self.MIN_STARTING_ID

                profile = {"legacy_cid": self.DUMMY_ID}
                self.insert_user(profile, "dummy@gmail.com", "dummy", last_follow)

                return last_follow

            if not isinstance(account.last_follow, int):
                return self.MIN_STARTING_ID
            return account.last_follow

    def update_latest_follow(self, last_follow: int) -> None:
        with ManagedSession() as db:
            if db.query(Account).count() == 0:
                return None

            account = db.query(Account).filter(Account.imvu_id == self.DUMMY_ID).first()

            if account is None:
                log.print_warn(f"Did not find dummy account in the database")
                return None

            account.last_follow = last_follow
            account.follow_time = func.now()

            try:
                db.add(account)
            except:
                log.print_fail(f"Failed to update database entry for dummy account")

    def get_usable_account_credentials(
        self, max_following: int, imvu_ids_to_ignore: T.List[int]
    ) -> T.Tuple[str, str]:
        with ManagedSession() as db:
            if db.query(Account).count() == 0:
                return ("", "")
            imvu_ids_to_ignore.append(self.DUMMY_ID)
            account = (
                db.query(Account)
                .filter(Account.imvu_id.notin_(imvu_ids_to_ignore))
                .filter(Account.followings < max_following)
                .first()
            )
            if account is None:
                return ("", "")

            log.print_normal(f"Found previous user {account.email}")
            return account.email, account.password
        return ("", "")

    def get_total_follows(self, imvu_id: int) -> T.Optional[int]:
        with ManagedSession() as db:
            if db.query(Account).count() == 0:
                return None

            account = db.query(Account).filter(Account.imvu_id == imvu_id).first()

            if account and account.followings is not None:
                return int(account.followings)
        return None
