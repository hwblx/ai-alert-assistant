"""Unit tests for alert fingerprint computation and payload identity stability.

What these tests cover:
- Deterministic fingerprint generation: Identical alert payloads consistently produce the
  exact same SHA-256 hexadecimal hash.
- Format compliance: The generated fingerprint strictly adheres to the 64-character hexadecimal
  format required by the `Fingerprint` schema constraint.
- Non-identity attribute invariance: Changes to non-identity alert fields (e.g., `description`,
  `summary`, `generator_url`, `status`, `event`, `started_at`) do not alter the calculated
  fingerprint, ensuring deduplication works across repeated or evolving alert occurrences.
- Identity attribute sensitivity: Modifying identity fields (`name` or `severity`) produces a
  distinct fingerprint, ensuring distinct alert conditions are never conflated.

How these tests are realized:
- Pure unit tests executed in sub-millisecond time with zero external I/O, database dependencies,
  or asynchronous runtime overhead.
- A baseline `AlertPayload` pytest fixture serves as the canonical test fixture.
- Pytest parameterization exercises targeted single-field mutations via `model_copy(update=...)`
  to independently assert invariance for non-identity fields and sensitivity for identity fields.
"""

import re
import pytest
from app.schemas import AlertPayload
from app.services.ingestion import compute_fingerprint

HEX_64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@pytest.fixture
def base_payload() -> AlertPayload:
    return AlertPayload(
        event="HighCPUUsage",
        name="high_cpu_cluster_a",
        severity="warning",
        status="firing",
        summary="CPU usage above 80%",
        description="Instance i-12345 running high",
        generator_url="https://monitoring.example.com",
        started_at="2026-10-25T13:00:00Z",
    )


def test_compute_fingerprint_deterministic_and_valid_format(base_payload: AlertPayload):
    copy_payload = base_payload.model_copy()

    fp1 = compute_fingerprint(base_payload)
    fp2 = compute_fingerprint(copy_payload)

    assert fp1 == fp2
    assert len(fp1) == 64
    assert HEX_64_PATTERN.fullmatch(fp1) is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Completely different description"),
        ("summary", "New summary text"),
        ("generator_url", "https://new-url.com"),
        ("status", "resolved"),
        ("event", "DifferentEventName"),
        ("started_at", "2026-10-25T14:00:00Z"),
    ],
)
def test_compute_fingerprint_ignores_non_identity_fields(
    base_payload: AlertPayload, field: str, value: str
):
    original_fp = compute_fingerprint(base_payload)
    modified_payload = base_payload.model_copy(update={field: value})

    assert compute_fingerprint(modified_payload) == original_fp


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "different_alert_name"),
        ("severity", "critical"),
    ],
)
def test_compute_fingerprint_changes_on_identity_fields(
    base_payload: AlertPayload, field: str, value: str
):
    original_fp = compute_fingerprint(base_payload)
    modified_payload = base_payload.model_copy(update={field: value})

    assert compute_fingerprint(modified_payload) != original_fp
