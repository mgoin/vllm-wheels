"""Small, explicit HTTP client used by scraper sources."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class FetchError(RuntimeError):
    url: str
    message: str
    status: int | None = None

    def __str__(self) -> str:
        detail = f"HTTP {self.status}" if self.status else self.message
        return f"{detail}: {self.url}"


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str = "vllm-wheel-index/2.0",
        timeout: float = 20,
        retries: int = 2,
        github_token: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.default_headers = {"User-Agent": user_agent}
        self.github_token = github_token

    def get_text(
        self,
        url: str,
        *,
        accept: str | None = None,
        github_api: bool = False,
    ) -> str:
        headers = dict(self.default_headers)
        if accept:
            headers["Accept"] = accept
        if github_api and self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        last_error: FetchError | None = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(url, headers=headers)
                with urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8")
            except HTTPError as error:
                last_error = FetchError(url, str(error.reason), error.code)
                if error.code not in {429, 500, 502, 503, 504}:
                    raise last_error from error
            except (URLError, TimeoutError) as error:
                last_error = FetchError(url, str(error.reason if isinstance(error, URLError) else error))

            if attempt < self.retries:
                time.sleep(0.4 * (2**attempt))

        assert last_error is not None
        raise last_error

    def get_json(
        self,
        url: str,
        *,
        github_api: bool = False,
    ) -> Any:
        text = self.get_text(
            url,
            accept="application/vnd.github+json" if github_api else "application/json",
            github_api=github_api,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise FetchError(url, f"invalid JSON ({error})") from error
