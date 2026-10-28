from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints


Fingerprint = Annotated[
    str,
    StringConstraints(
        min_length=64,
        max_length=64,
        pattern=r"^[a-fA-F0-9]{64}$",
    ),
]


class AlertStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    NOTIFYING = "notifying"
    COMPLETED = "completed"
    FAILED = "failed"


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    analysis_summary: str | None = None
    error_message: str | None = None


class AlertPayload(BaseModel):
    event: str
    name: str
    severity: str
    status: str
    summary: str | None = None
    description: str | None = None
    generator_url: str | None = None
    started_at: str | None = None


class IngestionResult(BaseModel):
    status: AlertStatus
    alert_id: int | None
    fingerprint: Fingerprint
    message: str


class SeverityLevel(str, Enum):
    """Used by the LLMOutput model."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ConfidenceLevel(str, Enum):
    """Used by the LLMOutput model."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertAssessment(BaseModel):
    """
    Used by Pydantic AI for defining the LLMs output constraints.
    """
    model_config = ConfigDict(use_attribute_docstrings=True)

    assessed_severity: SeverityLevel
    """
    Classifies severity based on the context provided by the payload.
    """

    root_cause_hypothesis: str
    """
    Explains what likely triggered the alert based on the symptoms and metric context.
    """

    recommended_actions: list[str]
    """
    A list of ordered steps an on-call engineer should take to mitigate the incident.
    """

    sanitized_summary: str
    """
    High-level markdown summary of the incident, omitting sensitive data like hostnames, 
    internal IP addresses, tokens or credentials.
    """

    confidence: ConfidenceLevel
    """
    Indicates how certain the model is about its root cause hypothesis.
    """


class AlertResponse(AlertAssessment):
    alert_metadata: dict[str, Any]
    """
    Selected metrics of the alert raw data 
    """
