from __future__ import annotations

import pytest
from xtr_stopwatch import Stopwatch

from tests.support.listeners import RecordingListener
from xtr_event_dispatcher import Event, EventDispatcher, LazyListener
from xtr_event_dispatcher.debug import ListenerInfo, WrappedListener


def _function(_event: object) -> None: ...


def test_nothing_is_recorded_before_it_runs() -> None:
    wrapped = WrappedListener(_function)

    assert not wrapped.was_called()
    assert not wrapped.stopped_propagation()
    assert wrapped.get_wrapped_listener() is _function


@pytest.mark.anyio
async def test_it_records_that_the_listener_ran() -> None:
    wrapped = WrappedListener(_function)

    await wrapped(Event(), "foo", object())

    assert wrapped.was_called()
    assert not wrapped.stopped_propagation()


@pytest.mark.anyio
async def test_it_records_that_the_listener_stopped_the_event() -> None:
    wrapped = WrappedListener(RecordingListener().post_foo)

    await wrapped(Event(), "foo", object())

    assert wrapped.stopped_propagation()


def test_its_info_asks_the_dispatcher_for_the_priority() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("foo", _function, 7)

    info = WrappedListener(_function, dispatcher).get_info("foo")

    assert info == ListenerInfo("foo", 7, f"{__name__}._function")


@pytest.mark.parametrize(
    ("listener", "pretty"),
    [
        (_function, f"{__name__}._function"),
        (RecordingListener().pre_foo, "tests.support.listeners.RecordingListener.pre_foo"),
        (RecordingListener(), "tests.support.listeners.RecordingListener.__call__"),
    ],
    ids=["function", "method", "callable-object"],
)
def test_it_names_the_listener_as_written(listener: object, pretty: str) -> None:
    assert callable(listener)
    assert WrappedListener(listener).get_pretty() == pretty


@pytest.mark.anyio
async def test_a_lazy_listener_is_named_after_what_it_built() -> None:
    async def factory() -> object:
        return _function

    lazy = LazyListener(factory)
    assert WrappedListener(lazy).get_pretty().startswith("LazyListener(")

    _ = await lazy.resolve()

    assert WrappedListener(lazy).get_pretty() == f"{__name__}._function"


@pytest.mark.anyio
async def test_a_run_is_an_event_listener_event_on_the_stopwatch() -> None:
    stopwatch = Stopwatch()
    stopwatch.open_section()
    wrapped = WrappedListener(_function, stopwatch=stopwatch)

    await wrapped(Event(), "foo", object())
    await wrapped(Event(), "foo", object())

    event = stopwatch.get_event(f"{__name__}._function")
    assert event.category == "event_listener"
    assert len(event.get_periods()) == 2
    assert not event.is_started()


@pytest.mark.anyio
async def test_outside_an_open_section_a_run_is_not_timed() -> None:
    stopwatch = Stopwatch()
    wrapped = WrappedListener(_function, stopwatch=stopwatch)

    await wrapped(Event(), "foo", object())

    assert stopwatch.get_section_events("__root__") == {}


@pytest.mark.anyio
async def test_a_raising_listener_still_stops_its_event() -> None:
    stopwatch = Stopwatch()
    stopwatch.open_section()

    def failing(_event: object) -> None:
        message = "boom"
        raise RuntimeError(message)

    wrapped = WrappedListener(failing, stopwatch=stopwatch)

    with pytest.raises(RuntimeError, match="boom"):
        await wrapped(Event(), "foo", object())

    assert not stopwatch.get_event(f"{__name__}.{failing.__qualname__}").is_started()


@pytest.mark.anyio
async def test_a_listener_resetting_the_stopwatch_still_closes_its_own_event() -> None:
    stopwatch = Stopwatch()
    stopwatch.open_section()

    def resetting(_event: object) -> None:
        stopwatch.reset()

    wrapped = WrappedListener(resetting, stopwatch=stopwatch)

    await wrapped(Event(), "foo", object())

    assert stopwatch.get_section_events("__root__") == {}
