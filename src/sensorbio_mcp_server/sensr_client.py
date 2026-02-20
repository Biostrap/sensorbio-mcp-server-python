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
DEFAULT_TOKEN_URL = "https://auth.getsensr.io/token"

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
    """Small HTTP client for Sensr.

    Supports two auth modes:
    - Org API key: Authorization: APIKey <token>
    - OAuth2 client_credentials: Authorization: Bearer <access_token>
    """

    api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_scope: str | None = None
    token_url: str = DEFAULT_TOKEN_URL

    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 30.0
    max_retries: int = 4

    # Global client-side throttling to avoid WAF/rate-limits.
    # Ensures at least this many seconds between requests per-process.
    min_interval_s: float = 0.4

    # In-memory token cache (per client instance)
    _access_token: str | None = None
    _access_token_expires_at: float | None = None

    @classmethod
    def from_env(cls) -> "SensrClient":
        # Prefer org token (APIKey auth) if present.
        org_token = os.getenv("SENSR_ORG_TOKEN")
        if org_token:
            base_url = os.getenv("SENSR_BASE_URL", DEFAULT_BASE_URL)
            return cls(api_key=org_token, base_url=base_url)

        # Otherwise fall back to OAuth2 client credentials.
        client_id = os.getenv("SENSR_CLIENT_ID")
        client_secret = os.getenv("SENSR_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise SensrError(
                "Missing auth env vars. Set either SENSR_ORG_TOKEN (org API key) or both "
                "SENSR_CLIENT_ID and SENSR_CLIENT_SECRET (OAuth2 client_credentials)."
            )

        scope = os.getenv("SENSR_SCOPE")
        token_url = os.getenv("SENSR_TOKEN_URL", DEFAULT_TOKEN_URL)
        base_url = os.getenv("SENSR_BASE_URL", DEFAULT_BASE_URL)
        return cls(
            oauth_client_id=client_id,
            oauth_client_secret=client_secret,
            oauth_scope=scope,
            token_url=token_url,
            base_url=base_url,
        )

    def auth_mode(self) -> str:
        return "org" if self.api_key else "oauth"

    def _get_access_token(self) -> str:
        if self.api_key:
            raise SensrError("Internal error: attempted OAuth token flow while using org API key")

        now = time.time()
        if (
            self._access_token
            and self._access_token_expires_at is not None
            and (self._access_token_expires_at - now) >= 60
        ):
            return self._access_token

        if not self.oauth_client_id or not self.oauth_client_secret:
            raise SensrError(
                "Missing OAuth client credentials. Set SENSR_CLIENT_ID and SENSR_CLIENT_SECRET."
            )

        data: dict[str, str] = {"grant_type": "client_credentials"}
        if self.oauth_scope:
            data["scope"] = self.oauth_scope

        # Do NOT log secrets; keep error messages terse.
        headers = {"Accept": "application/json"}
        with httpx.Client(timeout=httpx.Timeout(self.timeout_s), http2=True) as client:
            resp = client.post(
                self.token_url,
                data=data,
                auth=(self.oauth_client_id, self.oauth_client_secret),
                headers=headers,
            )

        if resp.status_code >= 400:
            raise SensrError(f"OAuth token request failed HTTP {resp.status_code}: {resp.text[:500]}")

        token_json = self._safe_json(resp)
        access_token = token_json.get("access_token")
        expires_in = token_json.get("expires_in")
        if not access_token:
            raise SensrError("OAuth token response missing access_token")

        try:
            expires_in_s = float(expires_in) if expires_in is not None else 3600.0
        except (TypeError, ValueError):
            expires_in_s = 3600.0

        self._access_token = str(access_token)
        self._access_token_expires_at = time.time() + expires_in_s
        return self._access_token

    def _client(self) -> httpx.Client:
        # All requests should accept JSON.
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"APIKey {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer {self._get_access_token()}"

        return httpx.Client(
            base_url=self.base_url,
            headers=headers,
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

        raise SensrError(
            f"Request failed after retries: {method} {path}. Last error: {last_exc}"
        )

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
