"""Exercise MCP tools against real Sensr API.

Requires:
- SENSR_API_KEY
- SENSR_TEST_USER_ID (Sameer's user_id)
Optionally:
- SENSR_TEST_EMAIL (for get_user_by_email)
- SENSR_TZ

Run:
  uv run python scripts/test_tools.py
"""

from __future__ import annotations

import os
import time
from pprint import pprint
from datetime import datetime, timedelta, timezone

from sensorbio_mcp_server.server import (
    get_activities,
    get_biometrics,
    get_calories,
    get_org_scores_summary,
    get_org_sleep_summary,
    get_scores,
    get_sleep,
    get_user_by_email,
    search_user,
)


def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def main() -> None:
    require_env("SENSR_API_KEY")
    user_id = require_env("SENSR_TEST_USER_ID")
    email = os.getenv("SENSR_TEST_EMAIL")

    print("\n== defaults (no date) ==")
    # avoid massive prints
    print({"sleep": get_sleep(user_id)["summary"], "scores": get_scores(user_id)["summary"]})
    time.sleep(0.6)
    print({"calories_keys": list(get_calories(user_id).keys())})
    time.sleep(0.6)

    print("\n== granularity default + explicit ==")
    print({"calories_default": list(get_calories(user_id).keys())})
    time.sleep(0.6)
    print({"calories_week": list(get_calories(user_id, granularity='week').keys())})
    time.sleep(0.6)

    print("\n== date range (last 3 days) ==")
    print(get_sleep(user_id, days=3)["summary"])
    time.sleep(0.6)
    print(get_scores(user_id, days=3)["summary"])
    time.sleep(0.6)

    print("\n== summary_only true/false ==")
    s1 = get_sleep(user_id, days=1, summary_only=True)
    time.sleep(0.6)
    s2 = get_sleep(user_id, days=1, summary_only=False)
    time.sleep(0.6)
    # crude size check
    print({"summary_only_bytes": len(str(s1)), "full_bytes": len(str(s2))})

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - int(timedelta(days=2).total_seconds() * 1000)

    print("\n== activities filter + pagination cursor extraction ==")
    a1 = get_activities(user_id, last_timestamp=start_ms, end_timestamp_ms=now_ms, limit=5)
    time.sleep(0.6)
    print({k: a1.get(k) for k in ("has_more", "next_cursor", "next_url")})
    print({"activities_n": len(a1.get("data") or [])})
    if a1.get("has_more") and a1.get("next_cursor"):
        a2 = get_activities(user_id, cursor=a1["next_cursor"], last_timestamp=start_ms, end_timestamp_ms=now_ms, limit=5)
        time.sleep(0.6)
        print({"activities_page2_n": len(a2.get("data") or [])})

    print("\n== biometrics filter + pagination cursor extraction ==")
    b1 = get_biometrics(user_id, last_timestamp=start_ms, end_timestamp_ms=now_ms, limit=5)
    time.sleep(0.6)
    print({k: b1.get(k) for k in ("has_more", "next_cursor", "next_url")})
    print({"biometrics_n": len(b1.get("data") or [])})
    if b1.get("has_more") and b1.get("next_cursor"):
        b2 = get_biometrics(user_id, cursor=b1["next_cursor"], last_timestamp=start_ms, end_timestamp_ms=now_ms, limit=5)
        time.sleep(0.6)
        print({"biometrics_page2_n": len(b2.get("data") or [])})

    if email:
        print("\n== user lookup by email ==")
        print(get_user_by_email(email))
        time.sleep(0.6)

        print("\n== search_user ==")
        r = search_user(email.split("@")[0], limit=5)
        time.sleep(0.6)
        print({"search_n": len(r.get("data") or [])})

    print("\n== bulk org tools (max_users=3, concurrency=1) ==")
    # keep under rate limits
    oss = get_org_sleep_summary(days=2, max_users=3, concurrency=1)
    time.sleep(0.6)
    ocs = get_org_scores_summary(days=2, max_users=3, concurrency=1)
    time.sleep(0.6)
    print({"org_sleep_users": len(oss.get('users') or []), "errors": len(oss.get('errors') or [])})
    print({"org_scores_users": len(ocs.get('users') or []), "errors": len(ocs.get('errors') or [])})


if __name__ == "__main__":
    main()
