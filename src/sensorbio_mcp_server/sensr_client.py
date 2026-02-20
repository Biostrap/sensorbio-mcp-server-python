from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Mapping
import threading

import httpx


DEFAULT_BASE_URL = "https://api.getsensr.io"

# Process-wide throttle state (per python process, shared across client instances).
_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class SensrError(RuntimeError):
    """Internal exception; tools should return standardized error dicts instead of raising."""


def error_dict(
    *,
    message: str,
    endpoint: str,
    method: str,
    status: int | None = None,
    headers: httpx.Headers | None = None,
    body_preview: str | None = None,
) -> dict[str, Any]:
    hdrs = _pick_headers_subset(headers) if headers is not None else None
    preview = body_preview
    if preview is not None and len(preview) > 1500:
        preview = preview[:1500] + "..."
    return {
        "error": {
            "message": message,
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "headers_subset": hdrs,
            "body_preview": preview,
        }
    }


def _pick_headers_subset(headers: httpx.Headers) -> dict[str, str]:
    keep = [
        "server",
        "via",
        "cf-ray",
        "x-request-id",
        "x-amz-cf-id",
        "x-cache",
        "content-type",
        "date",
    ]
    out: dict[str, str] = {}
    for k in keep:
        v = headers.get(k)
        if v is not None:
            out[k] = v
    return out


@dataclass
class SensrClient:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 30.0
    max_retries: int = 4
    # Global client-side throttling to avoid WAF/rate-limits.
    # Ensures at least this many seconds between requests per-process.
    min_interval_s: float = 0.4

    @classmethod
    def from_env(cls) -> "SensrClient":
        api_key = os.getenv("SENSR_API_KEY")
        if not api_key:
            raise SensrError(
                "Missing SENSR_API_KEY env var. Sensr uses header: Authorization: APIKey <token>."
            )
        base_url = os.getenv("SENSR_BASE_URL", DEFAULT_BASE_URL)
        return cls(api_key=api_key, base_url=base_url)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"APIKey {self.api_key}"},
            timeout=httpx.Timeout(self.timeout_s),
            http2=True,
        )

    def _throttle(self) -> None:
        global _LAST_REQUEST_AT
        if self.min_interval_s <= 0:
            return
        with _THROTTLE_LOCK:
            now = time.time()
            wait_s = (_LAST_REQUEST_AT + self.min_interval_s) - now
            if wait_s > 0:
                time.sleep(wait_s)
            _LAST_REQUEST_AT = time.time()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Makes an API request and returns parsed JSON.

        Retries transient errors (429/5xx/timeouts) with exponential backoff + jitter.

        NOTE: Tool functions should *not* let exceptions escape; catch SensrError/Exception
        and return `error_dict(...)`.
        """
        last_exc: Exception | None = None
        with self._client() as client:
            for attempt in range(self.max_retries + 1):
                try:
                    self._throttle()
                    resp = client.request(method, path, params=params)

                    if resp.status_code == 429:
                        # Respect Retry-After if present.
                        ra = resp.headers.get("retry-after")
                        if ra:
                            try:
                                time.sleep(float(ra))
                            except ValueError:
                                pass
                        raise SensrError(
                            f"Transient HTTP 429 for {method} {path}: {resp.text[:500]}"
                        )

                    if resp.status_code in (500, 502, 503, 504):
                        raise SensrError(
                            f"Transient HTTP {resp.status_code} for {method} {path}: {resp.text[:500]}"
                        )

                    if resp.status_code >= 400:
                        raise SensrError(
                            f"HTTP {resp.status_code} for {method} {path}: {resp.text[:1000]}"
                        )

                    return self._safe_json(resp)
                except (httpx.TimeoutException, httpx.NetworkError, SensrError) as e:
                    last_exc = e
                    if attempt >= self.max_retries:
                        break
                    # exponential backoff with jitter
                    sleep_s = (2**attempt) * 0.5 + random.random() * 0.25
                    time.sleep(sleep_s)

        raise SensrError(f"Request failed after retries: {method} {path}. Last error: {last_exc}")

    def debug_request(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Returns status, subset of headers, and a body preview for debugging TLS/WAF issues."""
        with self._client() as client:
            resp = client.get(path, params=params)
            preview = resp.text
            if len(preview) > 1500:
                preview = preview[:1500] + "..."
            return {
                "status": resp.status_code,
                "headers": _pick_headers_subset(resp.headers),
                "body_preview": preview,
            }

    def _safe_json(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            return resp.json()  # type: ignore[return-value]
        except json.JSONDecodeError:
            ctype = resp.headers.get("content-type", "")
            raise SensrError(
                f"Non-JSON response (content-type={ctype}) status={resp.status_code}: {resp.text[:1000]}"
            )
