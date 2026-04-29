from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class BaseEvent(BaseModel):
    """Base class for all events flowing between trading bot services.

    Subclasses MUST override the class-level constants ``event_type`` and
    ``event_version`` with non-empty strings; this is enforced at class
    definition time by ``__init_subclass__``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: ClassVar[str] = ""
    event_version: ClassVar[str] = ""

    event_id: UUID = Field(default_factory=uuid4)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    emitted_by: str
    correlation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for attr in ("event_type", "event_version"):
            value = getattr(cls, attr, None)
            if not isinstance(value, str) or not value:
                raise TypeError(
                    f"{cls.__name__} must define class-level constant "
                    f"{attr!r} as a non-empty string (got {value!r})"
                )

    @model_serializer(mode="wrap")
    def _serialize_with_class_constants(self, handler: Any) -> dict[str, Any]:
        cls = type(self)
        return {
            "event_type": cls.event_type,
            "event_version": cls.event_version,
            **handler(self),
        }
