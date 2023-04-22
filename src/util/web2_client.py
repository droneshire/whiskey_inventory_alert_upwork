import requests
import time
import typing as T

from yaspin import yaspin

from utils import logger, tor


@yaspin(text="Waiting...")
def wait(wait_time) -> None:
    time.sleep(wait_time)


MY_IP_URL = "http://icanhazip.com/"


class Web2Client:
    def __init__(
        self,
        base_url: str,
        rate_limit_delay: float = 5.0,
        use_proxy: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay

        if dry_run:
            logger.print_warn("Web2Client in dry run mode...")

        if use_proxy:
            self.requests = tor.get_tor_session()
        else:
            self.requests = requests

        if verbose:
            logger.print_bold(
                f"Web2Client IP (proxy={use_proxy}): {self.requests.get(MY_IP_URL).text.strip()}"
            )

    def _get_request(
        self,
        url: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> T.Any:
        if self.rate_limit_delay > 0.0:
            wait(self.rate_limit_delay)

        try:
            return self.requests.request(
                "GET", url, params=params, headers=headers, timeout=timeout
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def _post_request(
        self,
        url: str,
        json_data: T.Dict[str, T.Any] = {},
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
        delay: float = 5.0,
    ) -> T.Any:
        if self.dry_run:
            return {}

        if delay > 0.0:
            wait(delay)

        try:
            return self.requests.request(
                "POST",
                url,
                json=json_data,
                params=params,
                headers=headers,
                timeout=timeout,
            ).json()
        except KeyboardInterrupt:
            raise
        except:
            return {}

    def url_download(
        self,
        url: str,
        file_path: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> None:
        if self.dry_run:
            return

        try:
            content = self._get_request(url, headers, params, timeout).content
            with open(file_path, "wb") as f:
                f.write(content)
        except KeyboardInterrupt:
            raise
        except:
            return
