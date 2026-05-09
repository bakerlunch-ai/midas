import asyncio
import json
from unittest.mock import AsyncMock

from hello_svc.config import Settings
from hello_svc.heartbeat import publish_heartbeat


def _settings(**overrides):
    base = {
        "database_url": "postgresql://test/test",
        "redis_url": "redis://test",
        "nats_url": "nats://test:4222",
    }
    return Settings(**(base | overrides))


def test_publish_heartbeat_sends_to_subject_using_service_name():
    nc = AsyncMock()
    asyncio.run(publish_heartbeat(nc, _settings(service_name="data-svc")))
    nc.publish.assert_awaited_once()
    subject, _ = nc.publish.call_args.args
    assert subject == "events.heartbeat.data-svc"


def test_publish_heartbeat_payload_is_heartbeat_event_json():
    nc = AsyncMock()
    asyncio.run(publish_heartbeat(nc, _settings()))
    _, payload = nc.publish.call_args.args
    data = json.loads(payload.decode())
    assert data["event_type"] == "heartbeat"
    assert data["event_version"] == "1.0"
    assert data["service_name"] == "hello-svc"
    assert data["emitted_by"] == "hello-svc"
