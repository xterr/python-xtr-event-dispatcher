from __future__ import annotations

from tests.support.subscribers import Subscriber
from xtr_event_dispatcher import EventSubscriberInterface


def test_a_class_declaring_its_events_is_a_subscriber() -> None:
    assert isinstance(Subscriber(), EventSubscriberInterface)


def test_a_plain_object_is_not_a_subscriber() -> None:
    assert not isinstance(object(), EventSubscriberInterface)
