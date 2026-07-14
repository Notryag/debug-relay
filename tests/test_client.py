from pathlib import Path

import httpx
import pytest

from debugrelay.client import (
    ClientConfigurationError,
    ClientSettings,
    DebugRelayClient,
    DebugRelayClientError,
    normalize_base_url,
)


def client_for(handler):
    return DebugRelayClient(
        ClientSettings(base_url="https://debugrelay.example", token="test-token"),
        transport=httpx.MockTransport(handler),
    )


def test_base_url_requires_tls_for_non_loopback_hosts() -> None:
    assert normalize_base_url("http://127.0.0.1:8010") == "http://127.0.0.1:8010/"
    assert normalize_base_url("https://debugrelay.example/api") == "https://debugrelay.example/api/"
    with pytest.raises(ClientConfigurationError, match="HTTPS"):
        normalize_base_url("http://debugrelay.example")
    with pytest.raises(ClientConfigurationError, match="user information"):
        normalize_base_url("https://user:secret@debugrelay.example")
    with pytest.raises(ClientConfigurationError, match="whitespace"):
        ClientSettings(base_url="https://debugrelay.example", token="bad token")


def test_request_uses_bearer_auth_and_does_not_follow_redirects() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ISSUE-1"}, request=request)

    with client_for(handler) as client:
        assert client.get_json("api/issues/ISSUE-1") == {"id": "ISSUE-1"}
    assert seen[0].headers["authorization"] == "Bearer test-token"
    assert seen[0].headers["user-agent"].startswith("debugrelay-cli/")

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://other.example"}, request=request)

    with client_for(redirect_handler) as client:
        with pytest.raises(DebugRelayClientError) as raised:
            client.get_json("api/issues/ISSUE-1")
    assert raised.value.status_code == 302


def test_structured_api_error_is_preserved() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "request_id": "req-test",
                    "details": {"field": "summary"},
                }
            },
            request=request,
        )

    with client_for(handler) as client:
        with pytest.raises(DebugRelayClientError) as raised:
            client.get_json("api/issues/ISSUE-1")
    assert raised.value.code == "VALIDATION_ERROR"
    assert raised.value.request_id == "req-test"
    assert raised.value.details == {"field": "summary"}


def test_bundle_download_is_bounded_and_cleans_partial_file(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"bundle-bytes", request=request)

    destination = tmp_path / "bundle.zip"
    with client_for(handler) as client:
        with pytest.raises(DebugRelayClientError, match="size limit"):
            client.download_bundle("ISSUE-1", destination, max_bytes=4)
    assert not destination.exists()
    assert list(tmp_path.glob("*.part")) == []

    with client_for(handler) as client:
        assert client.download_bundle("ISSUE-1", destination, max_bytes=64) == 12
    assert destination.read_bytes() == b"bundle-bytes"
    with client_for(handler) as client:
        with pytest.raises(DebugRelayClientError, match="already exists"):
            client.download_bundle("ISSUE-1", destination, max_bytes=64)
