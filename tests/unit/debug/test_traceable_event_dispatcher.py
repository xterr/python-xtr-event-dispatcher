from __future__ import annotations

from typing import final

import pytest
from typing_extensions import override
from xtr_logging_contracts import AbstractLogger, Context, LevelLike

from tests.support.listeners import RecordingListener
from tests.support.subscribers import Subscriber
from xtr_event_dispatcher import Event, EventDispatcher
from xtr_event_dispatcher.debug import ListenerInfo, TraceableEventDispatcher

pytestmark = pytest.mark.anyio


@final
class _RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, object]]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        del level
        self.records.append((message, dict(context or {})))


def _one(_event: object) -> None: ...


def _two(_event: object) -> None: ...


@pytest.fixture
def inner() -> EventDispatcher:
    return EventDispatcher()


@pytest.fixture
def logger() -> _RecordingLogger:
    return _RecordingLogger()


@pytest.fixture
def traced(inner: EventDispatcher, logger: _RecordingLogger) -> TraceableEventDispatcher:
    return TraceableEventDispatcher(inner, logger)


async def test_it_counts_each_listener_that_ran(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one, 5)

    _ = await traced.dispatch(Event(), "foo")
    _ = await traced.dispatch(Event(), "foo")

    assert traced.get_called_listeners() == [ListenerInfo("foo", 5, f"{__name__}._one", 2)]


async def test_it_lists_the_listeners_that_did_not_run(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    stopper = RecordingListener()
    inner.add_listener("foo", stopper.post_foo, 10)
    inner.add_listener("foo", _two)
    inner.add_listener("bar", _one, 3)

    _ = await traced.dispatch(Event(), "foo")

    assert traced.get_not_called_listeners() == [
        ListenerInfo("bar", 3, f"{__name__}._one"),
        ListenerInfo("foo", 0, f"{__name__}._two"),
    ]


async def test_it_records_events_nobody_listened_to(traced: TraceableEventDispatcher) -> None:
    _ = await traced.dispatch(Event(), "nobody")

    assert traced.get_orphaned_events() == ["nobody"]


async def test_a_listener_receives_the_traceable_dispatcher(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    received: list[object] = []

    def listener(_event: object, _name: str, dispatcher: object) -> None:
        received.append(dispatcher)

    inner.add_listener("foo", listener)

    _ = await traced.dispatch(Event(), "foo")

    assert received == [traced]


async def test_it_logs_who_ran_who_stopped_and_who_was_skipped(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
    logger: _RecordingLogger,
) -> None:
    stopper = RecordingListener()
    inner.add_listener("foo", stopper.post_foo, 10)
    inner.add_listener("foo", _two)

    _ = await traced.dispatch(Event(), "foo")

    assert [message for message, _ in logger.records] == [
        'Notified event "{event}" to listener "{listener}".',
        'Listener "{listener}" stopped propagation of the event "{event}".',
        'Listener "{listener}" was not called for event "{event}".',
    ]
    assert logger.records[2][1] == {"event": "foo", "listener": f"{__name__}._two"}


async def test_it_logs_an_event_already_stopped(
    traced: TraceableEventDispatcher,
    logger: _RecordingLogger,
) -> None:
    event = Event()
    event.stop_propagation()

    _ = await traced.dispatch(event, "foo")

    assert logger.records[0] == (
        'The "{event}" event is already stopped. No listeners have been called.',
        {"event": "foo"},
    )


async def test_reset_forgets_everything(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one)
    _ = await traced.dispatch(Event(), "foo")
    _ = await traced.dispatch(Event(), "nobody")

    traced.reset()

    assert traced.get_called_listeners() == []
    assert traced.get_orphaned_events() == []


def test_changes_reach_the_wrapped_dispatcher(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    subscriber = Subscriber()

    traced.add_listener("foo", _one, 4)
    traced.add_subscriber(subscriber)

    assert inner.get_listener_priority("foo", _one) == 4
    assert traced.get_listeners("foo") == [_one]
    assert traced.get_listener_priority("foo", _one) == 4
    assert traced.has_listeners("pre.foo")
    assert set(traced.get_listeners()) == {"foo", "pre.foo", "post.foo"}

    traced.remove_listener("foo", _one)
    traced.remove_subscriber(subscriber)

    assert not inner.has_listeners()
