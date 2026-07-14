from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


REDACTED = "[REDACTED]"

SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization|cookie|"
    r"connection[_-]?string|database[_-]?url|private[_-]?key)",
    re.IGNORECASE,
)
AUTH_HEADER = re.compile(
    r"(?im)\b(authorization|proxy-authorization)\s*:\s*[^\r\n]+",
)
SECRET_ASSIGNMENT = re.compile(
    r"(?im)(\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|cookie)\b"
    r"\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
)
BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
URI_CREDENTIALS = re.compile(
    r"(?i)([a-z][a-z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@",
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
    r"-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.DOTALL,
)


@dataclass(frozen=True)
class SanitizedContent:
    data: bytes
    redaction_count: int


def sanitize_text(value: str) -> tuple[str, int]:
    total = 0

    value, count = AUTH_HEADER.subn(lambda match: f"{match.group(1)}: {REDACTED}", value)
    total += count
    value, count = SECRET_ASSIGNMENT.subn(lambda match: f"{match.group(1)}{REDACTED}", value)
    total += count
    value, count = BEARER_TOKEN.subn(f"Bearer {REDACTED}", value)
    total += count
    value, count = URI_CREDENTIALS.subn(
        lambda match: f"{match.group(1)}{REDACTED}:{REDACTED}@",
        value,
    )
    total += count
    value, count = PRIVATE_KEY.subn("[REDACTED PRIVATE KEY]", value)
    total += count
    return value, total


def sanitize_json(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        total = 0
        for key, item in value.items():
            if SENSITIVE_KEY.search(str(key)):
                sanitized[str(key)] = REDACTED
                total += 1
                continue
            sanitized_item, count = sanitize_json(item)
            sanitized[str(key)] = sanitized_item
            total += count
        return sanitized, total
    if isinstance(value, list):
        sanitized_items = []
        total = 0
        for item in value:
            sanitized_item, count = sanitize_json(item)
            sanitized_items.append(sanitized_item)
            total += count
        return sanitized_items, total
    if isinstance(value, str):
        return sanitize_text(value)
    return value, 0


def serialize_sanitized_content(content: Any, content_type: str) -> SanitizedContent:
    if content_type == "application/json" or content_type.endswith("+json"):
        sanitized, count = sanitize_json(content)
        data = (
            json.dumps(
                sanitized,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        return SanitizedContent(data=data, redaction_count=count)

    if not isinstance(content, str):
        raise ValueError("non-JSON evidence content must be a string")
    sanitized_text, count = sanitize_text(content)
    return SanitizedContent(data=sanitized_text.encode("utf-8"), redaction_count=count)
