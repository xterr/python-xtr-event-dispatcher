from __future__ import annotations

import contextvars
import subprocess
import sys
from typing import final

import anyio
import pytest
from typing_extensions import override
from xtr_logging_contracts import AbstractLogger, Context, LevelLike

from tests.support.listeners import RecordingListener
from tests.support.subscribers import Subscriber
from xtr_event_dispatcher import Event, EventDispatcher, LazyListener
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


async def test_a_lazy_listener_is_replaced_by_what_it_built_as_without_tracing(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    listener = RecordingListener()

    async def factory() -> object:
        return listener

    inner.add_listener("foo", LazyListener(factory, "pre_foo"))

    _ = await traced.dispatch(Event(), "foo")

    assert inner.get_listeners("foo") == [listener.pre_foo]
    assert listener.pre_foo_invoked


async def test_a_listener_removed_while_the_event_is_dispatched_does_not_run_for_it(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    ran: list[str] = []

    def second(_: object) -> None:
        ran.append("second")

    def first(_: object) -> None:
        ran.append("first")
        inner.remove_listener("foo", second)

    inner.add_listener("foo", first, 10)
    inner.add_listener("foo", second)

    _ = await traced.dispatch(Event(), "foo")

    assert ran == ["first"]


async def test_an_event_nobody_listens_to_is_recorded_once(
    traced: TraceableEventDispatcher,
) -> None:
    for name in ("foo", "bar", "foo"):
        _ = await traced.dispatch(Event(), name)

    assert traced.get_orphaned_events() == ["foo", "bar"]


async def test_two_concurrent_units_record_only_their_own_events(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("a", _one)
    inner.add_listener("b", _two)
    both_dispatched = anyio.Event()
    pending = {"count": 2}
    seen: dict[str, set[str]] = {}

    async def unit(event_name: str) -> None:
        traced.begin_unit()
        _ = await traced.dispatch(Event(), event_name)
        pending["count"] -= 1
        if pending["count"] == 0:
            both_dispatched.set()
        await both_dispatched.wait()
        seen[event_name] = {info.pretty for info in traced.get_called_listeners()}
        traced.end_unit()

    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(unit, "a")
        _ = task_group.start_soon(unit, "b")

    assert seen["a"] == {f"{__name__}._one"}
    assert seen["b"] == {f"{__name__}._two"}


async def test_reset_inside_a_unit_clears_only_the_units_trace(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one)
    _ = await traced.dispatch(Event(), "foo")

    traced.begin_unit()
    _ = await traced.dispatch(Event(), "foo")
    traced.reset()

    assert traced.get_called_listeners() == []

    traced.end_unit()

    assert traced.get_called_listeners() == [ListenerInfo("foo", 0, f"{__name__}._one", 1)]


async def test_recording_returns_to_the_instance_after_the_unit_ends(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one)

    traced.begin_unit()
    _ = await traced.dispatch(Event(), "foo")
    traced.end_unit()

    assert traced.get_called_listeners() == []

    _ = await traced.dispatch(Event(), "foo")

    assert traced.get_called_listeners() == [ListenerInfo("foo", 0, f"{__name__}._one", 1)]


async def test_a_copied_context_records_into_the_unit_it_still_points_at(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one)
    traced.begin_unit()
    context = contextvars.copy_context()

    async def dispatch_in_copy() -> None:
        _ = await traced.dispatch(Event(), "foo")

    # Drive the coroutine inside the copied context, the way a synchronous
    # endpoint run under a copied context would record into the open unit.
    coroutine = dispatch_in_copy()
    try:
        while True:
            context.run(coroutine.send, None)
    except StopIteration:
        pass

    assert traced.get_called_listeners() == [ListenerInfo("foo", 0, f"{__name__}._one", 1)]

    traced.end_unit()


async def test_a_unit_only_exists_while_it_is_open(
    inner: EventDispatcher,
    traced: TraceableEventDispatcher,
) -> None:
    inner.add_listener("foo", _one)

    traced.begin_unit()
    _ = await traced.dispatch(Event(), "foo")
    assert traced.get_called_listeners() == [ListenerInfo("foo", 0, f"{__name__}._one", 1)]
    traced.begin_unit()

    assert traced.get_called_listeners() == []

    traced.end_unit()


def test_the_debug_module_imports_without_the_service_contracts() -> None:
    program = (
        "import sys; sys.modules['xtr_service_contracts'] = None; import xtr_event_dispatcher.debug"
    )

    result = subprocess.run(  # noqa: S603 — the program is a fixed literal, not user input
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
