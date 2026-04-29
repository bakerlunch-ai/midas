from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class BaseEvent(BaseModel):
    """Base class for all events flowing between trading bot services."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    event_version: str
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    emitted_by: str
    correlation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
