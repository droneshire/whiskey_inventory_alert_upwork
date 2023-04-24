import requests
import time
import typing as T

from util import log, tor, wait

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
            log.print_warn("Web2Client in dry run mode...")

        if use_proxy:
            self.requests = tor.get_tor_session()
        else:
            self.requests = requests

        if verbose:
            log.print_bold(
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
            with self.requests.request(
                "GET", url, params=params, headers=headers, timeout=timeout, stream=True
            ) as r:
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except KeyboardInterrupt:
            raise
        except:
            return