from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from typing_extensions import override

from xtr_event_dispatcher import Event, EventSubscriberInterface, InvalidSubscriberError
from xtr_event_dispatcher._subscribed_events import (
    SubscribedListenerDeclaration,
    listeners_subscribed_by,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents


class _Placed(Event):
    pass


def _audit() -> None: ...


def _subscriber(events: Mapping[object, object]) -> type[EventSubscriberInterface]:
    """A subscriber declaring ``events`` as they are, shape unchecked, as hand-written code may."""

    class Declaring(EventSubscriberInterface):
        @classmethod
        @override
        def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
            return cast("Mapping[str | type, SubscribedEvents]", events)

    return Declaring


def test_a_method_name_declares_no_priority() -> None:
    declared = listeners_subscribed_by(_subscriber({"foo": "on_foo"}))

    assert declared == [SubscribedListenerDeclaration("foo", "on_foo", None)]


def test_a_pair_declares_a_priority() -> None:
    declared = listeners_subscribed_by(_subscriber({"foo": ("on_foo", 5)}))

    assert declared == [SubscribedListenerDeclaration("foo", "on_foo", 5)]


def test_an_event_class_is_read_as_its_name() -> None:
    declared = listeners_subscribed_by(_subscriber({_Placed: "on_placed"}))

    assert declared[0].event_name == f"{__name__}._Placed"


def test_ordering_targets_are_read_one_or_several() -> None:
    declared = listeners_subscribed_by(
        _subscriber(
            {"foo": {"method": "on_foo", "before": "app:Audit", "after": [_Placed, _audit]}}
        ),
    )

    assert declared[0].before == ("app:Audit",)
    assert declared[0].after == (_Placed, _audit)


@pytest.mark.parametrize(
    "spec",
    [
        5,
        ["on_foo", 5],
        ("on_foo", "high"),
        {"priority": 5},
        {"method": "on_foo", "priorty": 5},
        {"method": "on_foo", "priority": "high"},
        {"method": "on_foo", "before": [5]},
    ],
    ids=[
        "a-number",
        "a-number-in-a-list",
        "a-pair-without-a-priority",
        "no-method",
        "an-unknown-key",
        "a-priority-that-is-not-a-number",
        "a-target-that-is-not-a-listener",
    ],
)
def test_a_declaration_of_no_known_shape_is_refused(spec: object) -> None:
    with pytest.raises(InvalidSubscriberError) as raised:
        _ = listeners_subscribed_by(_subscriber({"foo": spec}))

    assert raised.value.subscriber.endswith("Declaring")
    assert raised.value.event_name == "foo"


def test_a_single_function_is_one_ordering_target() -> None:
    declared = listeners_subscribed_by(_subscriber({"foo": {"method": "on_foo", "before": _audit}}))

    assert declared[0].before == (_audit,)


def test_a_subscriber_returning_no_mapping_is_refused() -> None:
    subscriber = _subscriber(cast("Mapping[object, object]", cast("object", None)))

    with pytest.raises(InvalidSubscriberError, match="not a mapping") as raised:
        _ = listeners_subscribed_by(subscriber)

    assert raised.value.event_name is None
