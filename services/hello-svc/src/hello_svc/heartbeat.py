from nats.aio.client import Client as NATSClient

from bot_events import HeartbeatEvent
from hello_svc.config import Settings


async def publish_heartbeat(nc: NATSClient, settings: Settings) -> None:
    event = HeartbeatEvent(
        emitted_by=settings.service_name,
        service_name=settings.service_name,
    )
    subject = f"events.heartbeat.{settings.service_name}"
    payload = event.model_dump_json().encode()
    await nc.publish(subject, payload)
