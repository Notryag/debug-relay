from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from debugrelay import __version__


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DOWNLOAD_LIMIT = 256 * 1024 * 1024


class ClientConfigurationError(ValueError):
    """Raised when a CLI connection setting is unsafe or malformed."""


class DebugRelayClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "CLIENT_ERROR",
        status_code: int | None = None,
        request_id: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.details = details


def _is_loopback(hostname: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalize_base_url(value: str) -> str:
    """Validate a server URL before a bearer token is attached to requests."""

    if not value or value.strip() != value:
        raise ClientConfigurationError(
            "server URL must not be empty or contain surrounding whitespace"
        )
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ClientConfigurationError("server URL must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ClientConfigurationError("server URL must not contain user information")
    if parsed.query or parsed.fragment:
        raise ClientConfigurationError("server URL must not contain a query or fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ClientConfigurationError("server URL contains an invalid port") from exc
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ClientConfigurationError("remote server URLs must use HTTPS")
    return value.rstrip("/") + "/"


def _path_segment(value: str) -> str:
    if not value:
        raise ClientConfigurationError("resource ID must not be empty")
    return quote(value, safe="")


@dataclass(frozen=True)
class ClientSettings:
    base_url: str
    token: str
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        normalize_base_url(self.base_url)
        if not self.token or any(character.isspace() for character in self.token):
            raise ClientConfigurationError("bearer token must not be empty or contain whitespace")
        if self.timeout <= 0:
            raise ClientConfigurationError("timeout must be greater than zero")


class DebugRelayClient:
    """Small REST adapter used by the CLI and kept independent of FastAPI internals."""

    def __init__(
        self,
        settings: ClientSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=normalize_base_url(settings.base_url),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.token}",
                "User-Agent": f"debugrelay-cli/{__version__}",
            },
            follow_redirects=False,
            timeout=settings.timeout,
            transport=transport,
        )

    def __enter__(self) -> DebugRelayClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise DebugRelayClientError(
                "request timed out",
                code="REQUEST_TIMEOUT",
            ) from exc
        except httpx.RequestError as exc:
            raise DebugRelayClientError(
                "could not reach the DebugRelay server",
                code="REQUEST_FAILED",
            ) from exc
        if not 200 <= response.status_code < 300:
            raise self._response_error(response)
        return response

    @staticmethod
    def _response_error(response: httpx.Response) -> DebugRelayClientError:
        request_id = response.headers.get("x-request-id")
        code = f"HTTP_{response.status_code}"
        message = response.reason_phrase or "request failed"
        details: Any = None
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            error = payload["error"]
            code = str(error.get("code") or code)
            message = str(error.get("message") or message)
            request_id = str(error.get("request_id") or request_id or "") or None
            details = error.get("details")
        return DebugRelayClientError(
            message,
            code=code,
            status_code=response.status_code,
            request_id=request_id,
            details=details,
        )

    @staticmethod
    def _json_response(response: httpx.Response) -> Any:
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise DebugRelayClientError(
                "server returned an invalid JSON response",
                code="INVALID_RESPONSE",
            ) from exc

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._json_response(self._request("GET", path, params=params))

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        response = self._request("POST", path, json=payload)
        return self._json_response(response)

    def issue_path(self, issue_id: str, suffix: str = "") -> str:
        return f"api/issues/{_path_segment(issue_id)}{suffix}"

    def download_bundle(
        self,
        issue_id: str,
        destination: Path,
        *,
        overwrite: bool = False,
        max_bytes: int = DEFAULT_DOWNLOAD_LIMIT,
    ) -> int:
        if max_bytes < 1:
            raise ClientConfigurationError("download size limit must be greater than zero")
        if destination.exists() and not overwrite:
            raise DebugRelayClientError(
                f"output file already exists: {destination}",
                code="OUTPUT_EXISTS",
            )
        parent = destination.parent
        if not parent.exists() or not parent.is_dir():
            raise DebugRelayClientError(
                f"output directory does not exist: {parent}",
                code="OUTPUT_DIRECTORY_MISSING",
            )

        temporary_path: Path | None = None
        try:
            with self._client.stream("GET", self.issue_path(issue_id, "/bundle")) as response:
                if not 200 <= response.status_code < 300:
                    response.read()
                    raise self._response_error(response)
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        if int(content_length) > max_bytes:
                            raise DebugRelayClientError(
                                "bundle exceeds the configured download size limit",
                                code="DOWNLOAD_TOO_LARGE",
                                details={"max_bytes": max_bytes},
                            )
                    except ValueError:
                        pass
                fd, temporary_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.",
                    suffix=".part",
                    dir=parent,
                )
                temporary_path = Path(temporary_name)
                written = 0
                with os.fdopen(fd, "wb") as output:
                    for chunk in response.iter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise DebugRelayClientError(
                                "bundle exceeds the configured download size limit",
                                code="DOWNLOAD_TOO_LARGE",
                                details={"max_bytes": max_bytes},
                            )
                        output.write(chunk)
                os.replace(temporary_path, destination)
                temporary_path = None
                return written
        except httpx.TimeoutException as exc:
            raise DebugRelayClientError(
                "bundle download timed out",
                code="REQUEST_TIMEOUT",
            ) from exc
        except httpx.RequestError as exc:
            raise DebugRelayClientError(
                "could not reach the DebugRelay server",
                code="REQUEST_FAILED",
            ) from exc
        except OSError as exc:
            raise DebugRelayClientError(
                f"could not write output file: {destination}",
                code="OUTPUT_WRITE_FAILED",
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
