"""
Script that monitors the firestore database
under the "admin.health_monitor.reset" field path
for a boolean value of True. If the value is True,
then the script will reset the server by killing
any outstanding bot processes and restarting them.
"""

import os
import subprocess
import sys
import time
import typing as T

import dotenv

from firebase.firebase_admin import get_reset, set_reset
from util import log, wait

dotenv.load_dotenv(".env")

TIME_BETWEEN_CHECKS = 60 * 10


def try_to_kill_process() -> None:
    pidfile = os.environ.get("BOT_PIDFILE", "monitor_inventory.pid")
    try:
        with open(pidfile, "r") as infile:
            pid = int(infile.read())
            os.kill(pid, 9)
    except:
        pass


def reset_server() -> None:
    """Reset the server by killing all bot processes and restarting them."""
    log.print_fail("Resetting server...")
    try_to_kill_process()
    bot_start_command = os.environ.get("BOT_START_COMMAND", "")

    if not bot_start_command:
        log.print_fail_arrow("BOT_START_COMMAND not set in .env file.")
        sys.exit(1)

    # kinda sketchy, as we can execute arb code here from the `.env` file...
    subprocess.call(bot_start_command, shell=True)
    log.print_ok_arrow("Server reset complete.")


def check_firebase_for_reset() -> None:
    """Check the firestore database for a reset signal."""
    credentials_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    reset = get_reset(credentials_file=credentials_file)
    if reset:
        log.print_bright("Reset signal detected.")
        reset_server()
        set_reset(credentials_file=credentials_file, reset=False)
        log.print_ok_arrow("Bot reset complete.")


if __name__ == "__main__":
    dotenv.load_dotenv(".env")

    pidfile = os.environ.get("RESET_PIDFILE", "reset_server.pid")

    with open(pidfile, "w") as outfile:
        outfile.write(str(os.getpid()))

    while True:
        check_firebase_for_reset()
        wait.wait(TIME_BETWEEN_CHECKS)