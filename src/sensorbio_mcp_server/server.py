from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .sensr_client import SensrClient


mcp = FastMCP("sensorbio")


def _sensr() -> SensrClient:
    return SensrClient.from_env()


@mcp.tool()
def list_users(page: int = 1, limit: int = 100, search: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "limit": limit}
    if search:
        params["search"] = search
    return _sensr().request("GET", "/v1/organizations/users", params=params)


@mcp.tool()
def get_user_ids() -> dict[str, Any]:
    return _sensr().request("GET", "/v1/organizations/users/ids")


@mcp.tool()
def get_sleep(user_id: str, date: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if date:
        params["date"] = date
    return _sensr().request("GET", f"/v1/users/{user_id}/sleep", params=params)


@mcp.tool()
def get_scores(user_id: str, date: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if date:
        params["date"] = date
    return _sensr().request("GET", f"/v1/users/{user_id}/scores", params=params)


@mcp.tool()
def get_activities(user_id: str, last_timestamp: int = 0, limit: int = 50) -> dict[str, Any]:
    params: dict[str, Any] = {"last_timestamp": last_timestamp, "limit": limit}
    return _sensr().request("GET", f"/v1/users/{user_id}/activities", params=params)


@mcp.tool()
def get_biometrics(user_id: str, last_timestamp: int = 0, limit: int = 50) -> dict[str, Any]:
    params: dict[str, Any] = {"last_timestamp": last_timestamp, "limit": limit}
    return _sensr().request("GET", f"/v1/users/{user_id}/biometrics", params=params)


@mcp.tool()
def get_calories(user_id: str, date: str | None = None, granularity: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if date:
        params["date"] = date
    if granularity:
        params["granularity"] = granularity
    return _sensr().request("GET", f"/v1/users/{user_id}/calories", params=params)


@mcp.tool()
def debug_request(path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    # Allow passing full paths like "/v1/..."
    if not path.startswith("/"):
        path = "/" + path
    return _sensr().debug_request(path, params=query)


def main() -> None:
    mcp.run()
