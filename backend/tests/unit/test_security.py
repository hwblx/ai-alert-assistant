"""Unit tests for inbound webhook security and HMAC signature verification.

What these tests cover:
- Cryptographic verification of Hookdeck HMAC-SHA256 signatures across inbound webhook requests.
- Support for dual-header signature verification during Hookdeck signing secret rotations
  (`x-hookdeck-signature` and `x-hookdeck-signature-2`).
- Enforcement of fast-fail error handling:
  - HTTP 500 when the server lacks a configured signing secret.
  - HTTP 401 when signature headers are omitted.
  - HTTP 401 when signatures do not match the payload (tampered body or forged signature).
  - HTTP 401 when signature headers contain malformed values.

How these tests are realized:
- Pure unit tests executed in sub-millisecond time without spawning an HTTP server or database.
- A synthetic Starlette `Request` object is constructed with raw ASGI HTTP scopes and asynchronous
  body byte streams to exercise `verify_webhook` as an isolated FastAPI dependency.
- Pytest's `monkeypatch` fixture isolates test settings, ensuring `HOOKDECK_SIGNING_SECRET`
  does not leak across test runs.
"""

import base64
import hashlib
import hmac
from typing import Mapping

import pytest
from starlette.requests import Request

from app.api.webhooks import verify_webhook
from app.errors import (
    HOOKDECK_MISSING_SECRET,
    HOOKDECK_INVALID_SIGNATURE,
    HOOKDECK_MISSING_SIGNATURE,
)
from app.settings import settings

TEST_SECRET = "test_hookdeck_signing_secret_123"
SAMPLE_PAYLOAD = b'{"event":"HighCPUUsage","name":"high_cpu_alert"}'


def compute_signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def make_request(body: bytes, headers: Mapping[str, str]) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in headers.items()
    ]

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/webhooks",
        "headers": raw_headers,
    }
    return Request(scope, receive=receive)


@pytest.fixture(autouse=True)
def configure_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "HOOKDECK_SIGNING_SECRET", TEST_SECRET)


async def test_verify_webhook_valid_primary_signature():
    valid_sig = compute_signature(SAMPLE_PAYLOAD, TEST_SECRET)
    request = make_request(
        SAMPLE_PAYLOAD,
        {"x-hookdeck-signature": valid_sig},
    )

    await verify_webhook(request)


async def test_verify_webhook_valid_secondary_signature():
    valid_sig = compute_signature(SAMPLE_PAYLOAD, TEST_SECRET)
    request = make_request(
        SAMPLE_PAYLOAD,
        {
            "x-hookdeck-signature": "outdated_or_mismatched_signature",
            "x-hookdeck-signature-2": valid_sig,
        },
    )

    await verify_webhook(request)


async def test_verify_webhook_missing_signing_secret_raises_500(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "HOOKDECK_SIGNING_SECRET", None)
    request = make_request(
        SAMPLE_PAYLOAD,
        {"x-hookdeck-signature": "any_signature"},
    )

    with pytest.raises(type(HOOKDECK_MISSING_SECRET)) as exc_info:
        await verify_webhook(request)

    assert exc_info.value.status_code == HOOKDECK_MISSING_SECRET.status_code
    assert exc_info.value.detail == HOOKDECK_MISSING_SECRET.detail


async def test_verify_webhook_missing_signature_headers_raises_401():
    request = make_request(SAMPLE_PAYLOAD, {})

    with pytest.raises(type(HOOKDECK_MISSING_SIGNATURE)) as exc_info:
        await verify_webhook(request)

    assert exc_info.value.status_code == HOOKDECK_MISSING_SIGNATURE.status_code
    assert exc_info.value.detail == HOOKDECK_MISSING_SIGNATURE.detail


async def test_verify_webhook_invalid_signature_raises_401():
    tampered_payload = b'{"event":"TamperedEvent"}'
    invalid_sig = compute_signature(tampered_payload, TEST_SECRET)
    request = make_request(
        SAMPLE_PAYLOAD,
        {"x-hookdeck-signature": invalid_sig},
    )

    with pytest.raises(type(HOOKDECK_INVALID_SIGNATURE)) as exc_info:
        await verify_webhook(request)

    assert exc_info.value.status_code == HOOKDECK_INVALID_SIGNATURE.status_code
    assert exc_info.value.detail == HOOKDECK_INVALID_SIGNATURE.detail


async def test_verify_webhook_malformed_signature_raises_401():
    request = make_request(
        SAMPLE_PAYLOAD,
        {"x-hookdeck-signature": "not_even_base64!?"},
    )

    with pytest.raises(type(HOOKDECK_INVALID_SIGNATURE)) as exc_info:
        await verify_webhook(request)

    assert exc_info.value.status_code == HOOKDECK_INVALID_SIGNATURE.status_code
    assert exc_info.value.detail == HOOKDECK_INVALID_SIGNATURE.detail
