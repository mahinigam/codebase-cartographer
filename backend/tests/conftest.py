import pytest
import socket
from unittest.mock import MagicMock

# Block all HTTPX requests by injecting the httpx_mock fixture globally.
# pytest-httpx will automatically intercept and fail any request not explicitly mocked.
@pytest.fixture(autouse=True)
def block_httpx_requests(httpx_mock):
    pass

# Also block the old requests library just in case
@pytest.fixture(autouse=True)
def block_requests_library(monkeypatch):
    try:
        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: _raise_net_err())
        monkeypatch.setattr(requests, "post", lambda *a, **k: _raise_net_err())
    except ImportError:
        pass

def _raise_net_err():
    raise RuntimeError("Network access disabled (requests library blocked)")
