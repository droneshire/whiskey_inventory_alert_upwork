import time

from yaspin import yaspin


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)
