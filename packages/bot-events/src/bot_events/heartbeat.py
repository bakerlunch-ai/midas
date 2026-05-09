from bot_events.base import BaseEvent


class HeartbeatEvent(BaseEvent):
    """Emitted periodically by every service to signal it is alive.

    The NATS subject (``events.heartbeat.<service>``) carries routing;
    ``service_name`` is the canonical in-payload identifier.
    """

    event_type = "heartbeat"
    event_version = "1.0"

    service_name: str
