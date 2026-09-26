from __future__ import annotations

import pytest

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
