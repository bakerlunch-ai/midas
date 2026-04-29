import json

import pytest
from pydantic import ValidationError

from bot_events import BaseEvent


class GoodEvent(BaseEvent):
    event_type = "test.good"
    event_version = "1.0"


def test_properly_defined_subclass_works():
    event = GoodEvent(emitted_by="test-suite")
    assert event.event_type == "test.good"
    assert event.event_version == "1.0"
    assert event.emitted_by == "test-suite"


def test_subclass_missing_event_type_raises():
    with pytest.raises(TypeError, match="event_type"):

        class _MissingEventType(BaseEvent):
            event_version = "1.0"


def test_event_instance_is_frozen():
    event = GoodEvent(emitted_by="test-suite")
    with pytest.raises(ValidationError):
        event.emitted_by = "someone-else"


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        GoodEvent(emitted_by="test-suite", surprise="boo")


def test_json_serialization_includes_class_constants():
    event = GoodEvent(emitted_by="test-suite")
    data = json.loads(event.model_dump_json())
    assert data["event_type"] == "test.good"
    assert data["event_version"] == "1.0"
    assert data["emitted_by"] == "test-suite"
