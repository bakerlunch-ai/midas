import json

import pytest
from pydantic import ValidationError

from bot_events import HeartbeatEvent


def test_construction_with_required_fields_succeeds():
    event = HeartbeatEvent(emitted_by="hello-svc", service_name="hello-svc")
    assert event.emitted_by == "hello-svc"
    assert event.service_name == "hello-svc"


def test_event_type_is_heartbeat():
    event = HeartbeatEvent(emitted_by="hello-svc", service_name="hello-svc")
    assert event.event_type == "heartbeat"


def test_event_version_is_one_dot_zero():
    event = HeartbeatEvent(emitted_by="hello-svc", service_name="hello-svc")
    assert event.event_version == "1.0"


def test_service_name_is_required():
    with pytest.raises(ValidationError, match="service_name"):
        HeartbeatEvent(emitted_by="hello-svc")


def test_event_instance_is_frozen():
    event = HeartbeatEvent(emitted_by="hello-svc", service_name="hello-svc")
    with pytest.raises(ValidationError):
        event.service_name = "other-svc"


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        HeartbeatEvent(
            emitted_by="hello-svc",
            service_name="hello-svc",
            surprise="boo",
        )


def test_json_serialization_includes_class_constants_and_service_name():
    event = HeartbeatEvent(emitted_by="hello-svc", service_name="hello-svc")
    data = json.loads(event.model_dump_json())
    assert data["event_type"] == "heartbeat"
    assert data["event_version"] == "1.0"
    assert data["service_name"] == "hello-svc"
