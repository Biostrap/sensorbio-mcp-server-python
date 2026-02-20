import os

import pytest

from sensorbio_mcp_server.sensr_client import SensrClient, SensrError


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in [
        "SENSR_ORG_TOKEN",
        "SENSR_CLIENT_ID",
        "SENSR_CLIENT_SECRET",
        "SENSR_SCOPE",
        "SENSR_TOKEN_URL",
        "SENSR_BASE_URL",
    ]:
        monkeypatch.delenv(k, raising=False)


def test_from_env_prefers_org_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("SENSR_ORG_TOKEN", "org_token_value")
    # Even if oauth env vars are present, org token should win.
    monkeypatch.setenv("SENSR_CLIENT_ID", "cid")
    monkeypatch.setenv("SENSR_CLIENT_SECRET", "csecret")

    client = SensrClient.from_env()
    assert client.auth_mode() == "org"
    assert client.api_key == "org_token_value"


def test_from_env_uses_oauth_when_no_org_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("SENSR_CLIENT_ID", "cid")
    monkeypatch.setenv("SENSR_CLIENT_SECRET", "csecret")

    client = SensrClient.from_env()
    assert client.auth_mode() == "oauth"
    assert client.api_key is None
    assert client.oauth_client_id == "cid"


def test_from_env_missing_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(SensrError):
        SensrClient.from_env()
