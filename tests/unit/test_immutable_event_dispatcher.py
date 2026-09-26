from __future__ import annotations

import pytest

from tests.support.subscribers import Subscriber
from xtr_event_dispatcher import (
    BadMethodCallError,
    Event,
    EventDispatcher,
    ImmutableEventDispatcher,
)


@pytest.fixture
def inner() -> EventDispatcher:
    return EventDispatcher()


@pytest.fixture
def dispatcher(inner: EventDispatcher) -> ImmutableEventDispatcher:
    return ImmutableEventDispatcher(inner)


def _listener() -> None: ...


@pytest.mark.anyio
async def test_dispatch_goes_through_the_wrapped_dispatcher(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    received: list[tuple[object, str]] = []

    def listener(event: object, name: str) -> None:
        received.append((event, name))

    inner.add_listener("event", listener)
    event = Event()

    result = await dispatcher.dispatch(event, "event")

    assert result is event
    assert received == [(event, "event")]


def test_it_reads_the_wrapped_dispatchers_listeners(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    inner.add_listener("event", _listener, 7)

    assert dispatcher.get_listeners("event") == [_listener]
    assert dispatcher.get_listeners() == {"event": [_listener]}
    assert dispatcher.get_listener_priority("event", _listener) == 7
    assert dispatcher.has_listeners("event")
    assert dispatcher.has_listeners()


def test_adding_a_listener_is_refused(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    with pytest.raises(BadMethodCallError) as raised:
        dispatcher.add_listener("event", _listener)

    assert raised.value.method == "add_listener"
    assert not inner.has_listeners()


def test_adding_a_subscriber_is_refused(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    with pytest.raises(BadMethodCallError):
        dispatcher.add_subscriber(Subscriber())

    assert not inner.has_listeners()


def test_removing_a_listener_is_refused(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    inner.add_listener("event", _listener)

    with pytest.raises(BadMethodCallError):
        dispatcher.remove_listener("event", _listener)

    assert inner.has_listeners("event")


def test_removing_a_subscriber_is_refused(
    inner: EventDispatcher,
    dispatcher: ImmutableEventDispatcher,
) -> None:
    subscriber = Subscriber()
    inner.add_subscriber(subscriber)

    with pytest.raises(BadMethodCallError):
        dispatcher.remove_subscriber(subscriber)

    assert inner.has_listeners("pre.foo")
