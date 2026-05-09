import asyncio
import json
from unittest.mock import AsyncMock

from hello_svc.heartbeat import publish_heartbeat


def test_publish_heartbeat_sends_to_subject_using_service_name(settings_factory):
    nc = AsyncMock()
    asyncio.run(publish_heartbeat(nc, settings_factory(service_name="data-svc")))
    nc.publish.assert_awaited_once()
    subject, _ = nc.publish.call_args.args
    assert subject == "events.heartbeat.data-svc"


def test_publish_heartbeat_payload_is_heartbeat_event_json(settings_factory):
    nc = AsyncMock()
    asyncio.run(publish_heartbeat(nc, settings_factory()))
    _, payload = nc.publish.call_args.args
    data = json.loads(payload.decode())
    assert data["event_type"] == "heartbeat"
    assert data["event_version"] == "1.0"
    assert data["service_name"] == "hello-svc"
    assert data["emitted_by"] == "hello-svc"
