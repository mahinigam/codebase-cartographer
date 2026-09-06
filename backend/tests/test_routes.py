from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import routes
from app.core.config import settings


def test_api_token_is_optional_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", None)

    routes.require_api_token(None, None)


def test_api_token_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")

    with pytest.raises(HTTPException) as exc:
        routes.require_api_token(None, None)

    assert exc.value.status_code == 401


def test_api_token_accepts_bearer_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")

    routes.require_api_token("Bearer secret", None)


def test_scan_rate_limit_rejects_excess_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "scan_rate_limit_per_minute", 1)
    routes._rate_windows.clear()
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    routes._enforce_rate_limit(request)
    with pytest.raises(HTTPException) as exc:
        routes._enforce_rate_limit(request)

    assert exc.value.status_code == 429
