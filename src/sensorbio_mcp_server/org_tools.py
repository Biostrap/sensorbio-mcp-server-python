from __future__ import annotations

from typing import Any

import anyio

from .sensr_client import SensrClient, error_dict
from .utils import expand_date_range, make_range_summary, strip_sleep_payload


def _get_org_user_ids(client: SensrClient, max_users: int) -> list[str] | dict[str, Any]:
    try:
        resp = client.request("GET", "/v1/organizations/users/ids")
        data = resp.get("user_ids")
        if not isinstance(data, list):
            return error_dict(
                message="Unexpected response shape for user ids",
                endpoint="/v1/organizations/users/ids",
                method="GET",
                status=200,
                body_preview=str(resp)[:1500],
            )
        return [str(x) for x in data][:max_users]
    except Exception as e:
        return error_dict(
            message=f"{type(e).__name__}: {e}",
            endpoint="/v1/organizations/users/ids",
            method="GET",
        )


def org_sleep_summary(
    *,
    client: SensrClient,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    max_users: int = 50,
    concurrency: int = 5,
) -> dict[str, Any]:
    ids = _get_org_user_ids(client, max_users)
    if isinstance(ids, dict) and ids.get("error"):
        return ids

    dr = expand_date_range(date_str=date, start_date=start_date, end_date=end_date, days=days)
    users: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    async def fetch_user(uid: str) -> None:
        user_days: list[dict[str, Any]] = []
        for d in dr.dates:
            try:
                resp = client.request("GET", "/v1/sleep", params={"user_id": uid, "date": d})
                resp = strip_sleep_payload(resp)
                user_days.append({"date": d, "data": resp.get("data")})
            except Exception as e:
                errors.append(
                    error_dict(
                        message=f"{type(e).__name__}: {e}",
                        endpoint="/v1/sleep",
                        method="GET",
                    )
                )
        users.append({"user_id": uid, "days": user_days, "summary": make_range_summary(user_days)})

    async def runner() -> None:
        sem = anyio.Semaphore(concurrency)
        async with anyio.create_task_group() as tg:
            for uid in ids:  # type: ignore[assignment]
                async def _one(u: str = uid) -> None:
                    async with sem:
                        await fetch_user(u)

                tg.start_soon(_one)

    try:
        anyio.run(runner)
    except RuntimeError:
        # already in an event loop; run sequentially
        for uid in ids:  # type: ignore[assignment]
            anyio.run(fetch_user, uid)

    return {"range": {"dates": dr.dates, **make_range_summary([{ "date": d } for d in dr.dates])}, "users": users, "errors": errors}


def org_scores_summary(
    *,
    client: SensrClient,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    max_users: int = 50,
    concurrency: int = 5,
) -> dict[str, Any]:
    ids = _get_org_user_ids(client, max_users)
    if isinstance(ids, dict) and ids.get("error"):
        return ids

    dr = expand_date_range(date_str=date, start_date=start_date, end_date=end_date, days=days)
    users: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    async def fetch_user(uid: str) -> None:
        user_days: list[dict[str, Any]] = []
        for d in dr.dates:
            try:
                resp = client.request("GET", "/v1/scores", params={"user_id": uid, "date": d})
                user_days.append({"date": d, "data": resp.get("data")})
            except Exception as e:
                errors.append(
                    error_dict(
                        message=f"{type(e).__name__}: {e}",
                        endpoint="/v1/scores",
                        method="GET",
                    )
                )
        users.append({"user_id": uid, "days": user_days, "summary": make_range_summary(user_days)})

    async def runner() -> None:
        sem = anyio.Semaphore(concurrency)
        async with anyio.create_task_group() as tg:
            for uid in ids:  # type: ignore[assignment]
                async def _one(u: str = uid) -> None:
                    async with sem:
                        await fetch_user(u)

                tg.start_soon(_one)

    try:
        anyio.run(runner)
    except RuntimeError:
        for uid in ids:  # type: ignore[assignment]
            anyio.run(fetch_user, uid)

    return {"range": {"dates": dr.dates, **make_range_summary([{ "date": d } for d in dr.dates])}, "users": users, "errors": errors}
