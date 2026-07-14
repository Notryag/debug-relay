from __future__ import annotations

import json

from debugrelay.services.redaction import (
    REDACTED,
    sanitize_json,
    sanitize_text,
    serialize_sanitized_content,
)


def test_json_redaction_removes_sensitive_keys_and_values() -> None:
    content = {
        "password": "database-secret",
        "nested": {
            "authorization": "Bearer auth-secret",
            "message": "token=inline-secret request_id=request-1",
        },
        "request_id": "request-1",
    }

    sanitized, count = sanitize_json(content)

    assert sanitized["password"] == REDACTED
    assert sanitized["nested"]["authorization"] == REDACTED
    assert "inline-secret" not in sanitized["nested"]["message"]
    assert sanitized["request_id"] == "request-1"
    assert count == 3


def test_text_redaction_handles_headers_urls_and_private_keys() -> None:
    value = """Authorization: Bearer auth-secret
DATABASE_URL=postgresql://user:password@example.invalid/app
api_key=key-secret
-----BEGIN PRIVATE KEY-----
private-material
-----END PRIVATE KEY-----
"""

    sanitized, count = sanitize_text(value)

    assert "auth-secret" not in sanitized
    assert "password@example" not in sanitized
    assert "key-secret" not in sanitized
    assert "private-material" not in sanitized
    assert count == 4


def test_json_serialization_is_stable_and_sanitized() -> None:
    first = serialize_sanitized_content(
        {"z": 1, "password": "secret", "a": "safe"},
        "application/json",
    )
    second = serialize_sanitized_content(
        {"a": "safe", "password": "different", "z": 1},
        "application/json",
    )

    assert first.data == second.data
    assert first.redaction_count == 1
    assert json.loads(first.data)["password"] == REDACTED
