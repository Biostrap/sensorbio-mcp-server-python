from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


DEFAULT_TZ = "America/Chicago"


def get_tz(tz: str | None = None) -> ZoneInfo:
    name = tz or os.getenv("SENSR_TZ") or DEFAULT_TZ
    return ZoneInfo(name)


def today_str(*, tz: str | None = None) -> str:
    d = datetime.now(get_tz(tz)).date()
    return d.isoformat()


@dataclass(frozen=True)
class DateRange:
    dates: list[str]  # YYYY-MM-DD inclusive


def _parse_yyyy_mm_dd(s: str) -> date:
    return date.fromisoformat(s)


def expand_date_range(
    *,
    date_str: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
    tz: str | None = None,
) -> DateRange:
    """Expands supported date inputs into a list of YYYY-MM-DD strings.

    Rules:
    - If date_str is provided: single date.
    - Else if start_date/end_date provided: inclusive range.
    - Else if days provided: last N days ending today (inclusive).
    - Else: today.
    """
    provided = [p is not None for p in (date_str, start_date, end_date, days)]
    if sum(provided) == 0:
        date_str = today_str(tz=tz)

    if date_str is not None:
        d0 = _parse_yyyy_mm_dd(date_str)
        return DateRange(dates=[d0.isoformat()])

    if days is not None:
        if days <= 0:
            raise ValueError("days must be >= 1")
        end = _parse_yyyy_mm_dd(today_str(tz=tz))
        start = end - timedelta(days=days - 1)
        out: list[str] = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return DateRange(dates=out)

    if start_date is None or end_date is None:
        raise ValueError("start_date and end_date must be provided together")

    s = _parse_yyyy_mm_dd(start_date)
    e = _parse_yyyy_mm_dd(end_date)
    if e < s:
        raise ValueError("end_date must be >= start_date")

    out2: list[str] = []
    cur2 = s
    while cur2 <= e:
        out2.append(cur2.isoformat())
        cur2 += timedelta(days=1)
    return DateRange(dates=out2)


def cursor_from_next_link(next_url: str | None) -> str | None:
    if not next_url:
        return None
    try:
        qs = parse_qs(urlparse(next_url).query)
        for key in ("cursor", "page[cursor]", "page_cursor"):
            if key in qs and qs[key]:
                return qs[key][0]
        return None
    except Exception:
        return None


def strip_sleep_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Best-effort removal of verbose time-series arrays for sleep endpoint."""
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data")
    if isinstance(data, dict):
        for k in ["time_series", "timeseries", "series", "raw", "epochs"]:
            if k in data:
                data.pop(k, None)
        # nested common shapes
        if isinstance(data.get("sleep"), dict):
            for k in ["time_series", "timeseries", "series", "raw", "epochs"]:
                data["sleep"].pop(k, None)
    return payload


def make_range_summary(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    dates: list[str] = []
    count = 0
    for r in results:
        if isinstance(r, dict) and r.get("date"):
            dates.append(str(r["date"]))
        count += 1
    return {
        "days": count,
        "start_date": min(dates) if dates else None,
        "end_date": max(dates) if dates else None,
    }
