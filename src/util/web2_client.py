import time
import typing as T

import requests

from util import log, wait

MY_IP_URL = "http://icanhazip.com/"


class Web2Client:
    def __init__(
        self,
        base_url: str = "",
        rate_limit_delay: float = 5.0,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay

        if dry_run:
            log.print_warn("Web2Client in dry run mode...")

        self.requests = requests

    def _get_request(
        self,
        url: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> T.Any:
        if self.rate_limit_delay > 0.0:
            wait.wait(self.rate_limit_delay)

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
            wait.wait(delay)

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
            log.format_fail(f"Failed to post to {url}")
            return {}

    def url_download(
        self,
        url: str,
        file_path: str,
        data: str,
        headers: T.Dict[str, T.Any] = {},
        params: T.Dict[str, T.Any] = {},
        timeout: float = 5.0,
    ) -> None:
        if self.dry_run:
            return

        try:
            with self.requests.request(
                "GET",
                url,
                data=data,
                params=params,
                headers=headers,
                timeout=timeout,
                stream=True,
                allow_redirects=True,
            ) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except KeyboardInterrupt:
            raise
        except:
            log.format_fail(f"Failed to download {url} to {file_path}")
            return
