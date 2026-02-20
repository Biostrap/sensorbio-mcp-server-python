from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .org_tools import org_scores_summary, org_sleep_summary
from .sensr_client import SensrClient, SensrError, error_dict
from .utils import cursor_from_next_link, expand_date_range, make_range_summary, strip_sleep_payload, today_str


mcp = FastMCP("sensorbio")


def _sensr() -> SensrClient:
    return SensrClient.from_env()


def _std_error(e: Exception, *, endpoint: str, method: str, status: int | None = None) -> dict[str, Any]:
    return error_dict(
        message=f"{type(e).__name__}: {e}",
        endpoint=endpoint,
        method=method,
        status=status,
    )


@mcp.tool(
    description=(
        "List organization users.\n\n"
        "Params:\n"
        "- page (int, default 1)\n"
        "- limit (int, default 100)\n"
        "- search (str, optional): substring query\n\n"
        "Returns: Sensr /v1/organizations/users response"
    )
)
def list_users(page: int = 1, limit: int = 100, search: str | None = None) -> dict[str, Any]:
    try:
        params: dict[str, Any] = {"page": page, "items_per_page": limit}
        if search:
            params["q"] = search
        return _sensr().request("GET", "/v1/organizations/users", params=params)
    except Exception as e:
        return _std_error(e, endpoint="/v1/organizations/users", method="GET")


@mcp.tool(description="Get all organization user IDs. Returns /v1/organizations/users/ids")
def get_user_ids() -> dict[str, Any]:
    try:
        return _sensr().request("GET", "/v1/organizations/users/ids")
    except Exception as e:
        return _std_error(e, endpoint="/v1/organizations/users/ids", method="GET")


@mcp.tool(
    description=(
        "Find a user by email (exact match preferred).\n\n"
        "Params:\n"
        "- email (str, required)\n\n"
        "Returns: {data: user|null} or {error:...}"
    )
)
def get_user_by_email(email: str) -> dict[str, Any]:
    try:
        client = _sensr()
        page = 1
        while page <= 50:
            resp = client.request(
                "GET",
                "/v1/organizations/users",
                params={"page": page, "items_per_page": 200, "q": email},
            )
            users = resp.get("data")
            if isinstance(users, list):
                for u in users:
                    if isinstance(u, dict) and str(u.get("email", "")).lower() == email.lower():
                        return {"data": u}
            meta = resp.get("meta")
            if isinstance(meta, dict) and meta.get("current_page") and meta.get("total_pages"):
                if meta["current_page"] >= meta["total_pages"]:
                    break
            if not users:
                break
            page += 1
        return {"data": None}
    except Exception as e:
        return _std_error(e, endpoint="/v1/organizations/users", method="GET")


@mcp.tool(
    description=(
        "Search for users by a free-text query (name/email).\n\n"
        "Params:\n"
        "- query (str, required)\n"
        "- page (int, default 1)\n"
        "- limit (int, default 50)\n\n"
        "Returns: Sensr /v1/organizations/users response"
    )
)
def search_user(query: str, page: int = 1, limit: int = 50) -> dict[str, Any]:
    try:
        return _sensr().request(
            "GET",
            "/v1/organizations/users",
            params={"page": page, "items_per_page": limit, "q": query},
        )
    except Exception as e:
        return _std_error(e, endpoint="/v1/organizations/users", method="GET")


@mcp.tool(
    description=(
        "Get sleep for a user.\n\n"
        "Accepted date inputs (mutually exclusive):\n"
        "- date (YYYY-MM-DD, optional; default: today in SENSR_TZ or America/Chicago)\n"
        "- OR start_date/end_date (YYYY-MM-DD, inclusive)\n"
        "- OR days (int >=1): last N days ending today\n\n"
        "Other params:\n"
        "- summary_only (bool, default true): if true, strips verbose time-series\n\n"
        "Returns: {range, results:[{date,data}], summary}"
    )
)
def get_sleep(
    user_id: str,
    date: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    summary_only: bool = True,
) -> dict[str, Any]:
    try:
        dr = expand_date_range(date_str=date, start_date=start_date, end_date=end_date, days=days)
        client = _sensr()
        results: list[dict[str, Any]] = []
        for d in dr.dates:
            resp = client.request("GET", "/v1/sleep", params={"user_id": user_id, "date": d})
            if summary_only:
                resp = strip_sleep_payload(resp)
            results.append({"date": d, "data": resp.get("data")})
        return {"range": {"dates": dr.dates}, "results": results, "summary": make_range_summary(results)}
    except Exception as e:
        return _std_error(e, endpoint="/v1/sleep", method="GET")


@mcp.tool(
    description=(
        "Get scores for a user.\n\n"
        "Accepted date inputs (mutually exclusive):\n"
        "- date (YYYY-MM-DD, optional; default: today in SENSR_TZ or America/Chicago)\n"
        "- OR start_date/end_date (YYYY-MM-DD, inclusive)\n"
        "- OR days (int >=1): last N days ending today\n\n"
        "Returns: {range, results:[{date,data}], summary}"
    )
)
def get_scores(
    user_id: str,
    date: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
) -> dict[str, Any]:
    try:
        dr = expand_date_range(date_str=date, start_date=start_date, end_date=end_date, days=days)
        client = _sensr()
        results: list[dict[str, Any]] = []
        for d in dr.dates:
            resp = client.request("GET", "/v1/scores", params={"user_id": user_id, "date": d})
            results.append({"date": d, "data": resp.get("data")})
        return {"range": {"dates": dr.dates}, "results": results, "summary": make_range_summary(results)}
    except Exception as e:
        return _std_error(e, endpoint="/v1/scores", method="GET")


@mcp.tool(
    description=(
        "Get activities for a user with optional date/timestamp filtering.\n\n"
        "Params:\n"
        "- user_id (str, required)\n"
        "- start_date/end_date (YYYY-MM-DD, optional): filter by activity timestamp\n"
        "- start_timestamp_ms/end_timestamp_ms (int, optional): filter by ms since epoch\n"
        "- cursor (str, optional): pagination cursor\n"
        "- limit (int, default 50)\n\n"
        "Returns: {data, next_cursor, has_more, next_url}"
    )
)
def get_activities(
    user_id: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    start_timestamp_ms: int | None = None,
    end_timestamp_ms: int | None = None,
    cursor: str | None = None,
    last_timestamp: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    endpoint = "/v1/activities"
    try:
        # Endpoint requires last-timestamp; use provided, else start_timestamp_ms, else 0.
        lt = last_timestamp
        if lt is None:
            lt = start_timestamp_ms if start_timestamp_ms is not None else 0

        params: dict[str, Any] = {"user_id": user_id, "limit": limit, "last-timestamp": lt}
        if cursor:
            params["cursor"] = cursor

        # These may or may not be supported server-side; if unsupported, API returns 400.
        if end_timestamp_ms is not None:
            params["end-timestamp"] = end_timestamp_ms
        if start_date is not None:
            params["start-date"] = start_date
        if end_date is not None:
            params["end-date"] = end_date

        resp = _sensr().request("GET", endpoint, params=params)
        data = resp.get("data")
        links = resp.get("links")
        next_url = None
        if isinstance(links, dict):
            next_url = links.get("next")
        next_cursor = cursor_from_next_link(next_url) if isinstance(next_url, str) else None
        has_more = bool(next_url or next_cursor)

        return {"data": data, "next_cursor": next_cursor, "has_more": has_more, "next_url": next_url}
    except Exception as e:
        return _std_error(e, endpoint=endpoint, method="GET")


@mcp.tool(
    description=(
        "Get biometrics for a user with optional date/timestamp filtering.\n\n"
        "Params:\n"
        "- user_id (str, required)\n"
        "- start_date/end_date (YYYY-MM-DD, optional)\n"
        "- start_timestamp_ms/end_timestamp_ms (int, optional)\n"
        "- cursor (str, optional)\n"
        "- limit (int, default 50)\n\n"
        "Returns: {data, next_cursor, has_more, next_url}"
    )
)
def get_biometrics(
    user_id: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    start_timestamp_ms: int | None = None,
    end_timestamp_ms: int | None = None,
    cursor: str | None = None,
    last_timestamp: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    endpoint = "/v1/biometrics"
    try:
        lt = last_timestamp
        if lt is None:
            lt = start_timestamp_ms if start_timestamp_ms is not None else 0

        params: dict[str, Any] = {"user_id": user_id, "limit": limit, "last-timestamp": lt}
        if cursor:
            params["cursor"] = cursor

        if end_timestamp_ms is not None:
            params["end-timestamp"] = end_timestamp_ms
        if start_date is not None:
            params["start-date"] = start_date
        if end_date is not None:
            params["end-date"] = end_date

        resp = _sensr().request("GET", endpoint, params=params)
        data = resp.get("data")
        links = resp.get("links")
        next_url = None
        if isinstance(links, dict):
            next_url = links.get("next")
        next_cursor = cursor_from_next_link(next_url) if isinstance(next_url, str) else None
        has_more = bool(next_url or next_cursor)

        return {"data": data, "next_cursor": next_cursor, "has_more": has_more, "next_url": next_url}
    except Exception as e:
        return _std_error(e, endpoint=endpoint, method="GET")


@mcp.tool(
    description=(
        "Get calorie details for a user.\n\n"
        "Params:\n"
        "- user_id (str, required)\n"
        "- date (YYYY-MM-DD, optional; default: today in SENSR_TZ or America/Chicago)\n"
        "- granularity (enum str, optional; default 'day'): day|week|month|year\n\n"
        "Returns: Sensr /v1/calorie/details response"
    )
)
def get_calories(
    user_id: str,
    date: str | None = None,
    granularity: str = "day",
) -> dict[str, Any]:
    endpoint = "/v1/calorie/details"
    try:
        if date is None:
            date = today_str()
        if granularity not in ("day", "week", "month", "year"):
            return error_dict(
                message="Invalid granularity; must be one of: day|week|month|year",
                endpoint=endpoint,
                method="GET",
                status=400,
            )
        params: dict[str, Any] = {"user_id": user_id, "date": date, "granularity": granularity}
        return _sensr().request("GET", endpoint, params=params)
    except Exception as e:
        return _std_error(e, endpoint=endpoint, method="GET")


@mcp.tool(
    description=(
        "Bulk: sleep summary across users in the org.\n\n"
        "Date selection (mutually exclusive): date OR (start_date+end_date) OR days.\n"
        "Params:\n"
        "- date (YYYY-MM-DD, optional; default today)\n"
        "- start_date/end_date (YYYY-MM-DD, optional)\n"
        "- days (int>=1, optional)\n"
        "- max_users (int, default 50)\n"
        "- concurrency (int, default 5)\n\n"
        "Returns: {range, users:[{user_id,days:[{date,data}],summary}], errors}"
    )
)
def get_org_sleep_summary(
    date: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    max_users: int = 50,
    concurrency: int = 3,
) -> dict[str, Any]:
    try:
        return org_sleep_summary(
            client=_sensr(),
            date=date,
            start_date=start_date,
            end_date=end_date,
            days=days,
            max_users=max_users,
            concurrency=concurrency,
        )
    except Exception as e:
        return _std_error(e, endpoint="/v1/sleep", method="GET")


@mcp.tool(
    description=(
        "Bulk: scores summary across users in the org.\n\n"
        "Date selection (mutually exclusive): date OR (start_date+end_date) OR days.\n"
        "Params:\n"
        "- date (YYYY-MM-DD, optional; default today)\n"
        "- start_date/end_date (YYYY-MM-DD, optional)\n"
        "- days (int>=1, optional)\n"
        "- max_users (int, default 50)\n"
        "- concurrency (int, default 5)\n\n"
        "Returns: {range, users:[{user_id,days:[{date,data}],summary}], errors}"
    )
)
def get_org_scores_summary(
    date: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    max_users: int = 50,
    concurrency: int = 3,
) -> dict[str, Any]:
    try:
        return org_scores_summary(
            client=_sensr(),
            date=date,
            start_date=start_date,
            end_date=end_date,
            days=days,
            max_users=max_users,
            concurrency=concurrency,
        )
    except Exception as e:
        return _std_error(e, endpoint="/v1/scores", method="GET")


@mcp.tool(
    description=(
        "Low-level debugging helper: make a GET request and return {status, headers_subset, body_preview}.\n\n"
        "Params:\n"
        "- path (str, required): may be '/v1/...' or 'v1/...'\n"
        "- query (dict[str,str], optional)"
    )
)
def debug_request(path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        if not path.startswith("/"):
            path = "/" + path
        return _sensr().debug_request(path, params=query)
    except Exception as e:
        return _std_error(e, endpoint=path, method="GET")


def main() -> None:
    mcp.run()
