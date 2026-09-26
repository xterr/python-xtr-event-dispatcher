"""What a scoped dispatcher adds; everything a dispatcher does is in test_event_dispatcher."""

from __future__ import annotations

import pytest

from xtr_event_dispatcher import (
    Event,
    EventDispatcher,
    ImmutableEventDispatcher,
    LazyListener,
    ScopedEventDispatcher,
)


@pytest.fixture
def parent() -> EventDispatcher:
    return EventDispatcher()


@pytest.fixture
def dispatcher(parent: EventDispatcher) -> ScopedEventDispatcher:
    return ScopedEventDispatcher(parent)


@pytest.mark.anyio
async def test_the_wrapped_dispatcher_is_left_as_it_was(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    def listener() -> None: ...

    dispatcher.add_listener("pre.foo", listener)

    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert parent.get_listeners() == {}
    assert not parent.has_listeners("pre.foo")
    assert parent.get_listener_priority("pre.foo", listener) is None


@pytest.mark.anyio
async def test_the_wrapped_dispatchers_listeners_run_too(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    called: list[str] = []
    parent.add_listener("pre.foo", lambda: called.append("parent"))
    dispatcher.add_listener("pre.foo", lambda: called.append("scoped"))

    _ = await dispatcher.dispatch(Event(), "pre.foo")
    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert called == ["parent", "scoped", "parent", "scoped"]


@pytest.mark.anyio
async def test_the_wrapped_dispatchers_listeners_keep_their_priority(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    called: list[str] = []
    parent.add_listener("pre.foo", lambda: called.append("high"), 10)
    parent.add_listener("pre.foo", lambda: called.append("low"), -10)
    dispatcher.add_listener("pre.foo", lambda: called.append("scoped"))

    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert called == ["high", "scoped", "low"]


@pytest.mark.anyio
async def test_an_event_with_nothing_added_here_is_dispatched_by_the_wrapped_one(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    received: list[object] = []

    def listener(_event: object, _name: str, source: object) -> None:
        received.append(source)

    parent.add_listener("pre.foo", listener)

    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert received == [parent]
    assert dispatcher.get_listeners("post.foo") == []


def test_listeners_read_from_both_dispatchers(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    def from_parent() -> None: ...
    def scoped() -> None: ...
    def other() -> None: ...

    parent.add_listener("pre.foo", from_parent, 10)
    dispatcher.add_listener("pre.foo", scoped)
    dispatcher.add_listener("post.foo", other)

    assert dispatcher.get_listeners("pre.foo") == [from_parent, scoped]
    assert dispatcher.get_listeners() == {"pre.foo": [from_parent, scoped], "post.foo": [other]}
    assert dispatcher.get_listener_priority("pre.foo", from_parent) == 10
    assert dispatcher.get_listener_priority("pre.foo", scoped) == 0
    assert dispatcher.has_listeners("pre.foo")
    assert dispatcher.has_listeners()


@pytest.mark.anyio
async def test_stopping_the_event_skips_the_wrapped_dispatchers_listeners(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    called: list[None] = []
    parent.add_listener("pre.foo", lambda: called.append(None), -10)
    dispatcher.add_listener("pre.foo", Event.stop_propagation)

    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert called == []


@pytest.mark.anyio
async def test_it_adds_listeners_next_to_a_dispatcher_that_cannot_change(
    parent: EventDispatcher,
) -> None:
    called: list[str] = []
    parent.add_listener("pre.foo", lambda: called.append("shared"))
    dispatcher = ScopedEventDispatcher(ImmutableEventDispatcher(parent))

    dispatcher.add_listener("pre.foo", lambda: called.append("scoped"))
    _ = await dispatcher.dispatch(Event(), "pre.foo")

    assert called == ["shared", "scoped"]


@pytest.mark.anyio
async def test_a_lazy_listener_copied_from_the_wrapped_dispatcher_is_built_once(
    parent: EventDispatcher,
    dispatcher: ScopedEventDispatcher,
) -> None:
    calls: list[None] = []

    async def factory() -> object:
        calls.append(None)
        return lambda: None

    parent.add_listener("pre.foo", LazyListener(factory))
    dispatcher.add_listener("pre.foo", lambda: None)

    _ = await dispatcher.dispatch(Event(), "pre.foo")
    _ = await parent.dispatch(Event(), "pre.foo")

    assert len(calls) == 1
