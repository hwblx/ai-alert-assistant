from typing import Any
from datetime import datetime, UTC

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

from app.schemas import AlertStatus, Fingerprint


class Alert(SQLModel, table=True):
    __tablename__: str = "alerts"

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: Fingerprint = Field(nullable=False, index=True)
    name: str
    source: str = Field(default="generic", index=True) 
    created_at: datetime = Field(default_factory=lambda:datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda:datetime.now(UTC))
    status: AlertStatus = Field(default=AlertStatus.PENDING)
    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    analysis_summary: str | None = None
    error_message: str | None = None

