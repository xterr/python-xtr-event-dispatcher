from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.subscribers import Subscriber
from xtr_event_dispatcher import BadMethodCallError, CompiledEventDispatcher, Event, LazyListener

if TYPE_CHECKING:
    from collections.abc import Callable


def _listener() -> None: ...


@pytest.mark.anyio
async def test_it_runs_the_listeners_it_was_built_with_by_priority() -> None:
    order: list[str] = []
    dispatcher = CompiledEventDispatcher(
        {"foo": [(lambda: order.append("low"), -5), (lambda: order.append("high"), 5)]},
    )

    _ = await dispatcher.dispatch(Event(), "foo")

    assert order == ["high", "low"]


@pytest.mark.anyio
async def test_a_listener_receives_the_compiled_dispatcher() -> None:
    received: list[object] = []

    def listener(_event: object, _name: str, dispatcher: object) -> None:
        received.append(dispatcher)

    dispatcher = CompiledEventDispatcher({"foo": [(listener, 0)]})

    _ = await dispatcher.dispatch(Event(), "foo")

    assert received == [dispatcher]


def test_a_lazy_listener_is_not_built_by_building_the_dispatcher() -> None:
    calls: list[None] = []

    async def factory() -> object:
        calls.append(None)
        return _listener

    dispatcher = CompiledEventDispatcher({"foo": [(LazyListener(factory), 0)]})

    assert dispatcher.has_listeners("foo")
    assert calls == []


def _add_listener(dispatcher: CompiledEventDispatcher) -> None:
    dispatcher.add_listener("foo", _listener)


def _add_subscriber(dispatcher: CompiledEventDispatcher) -> None:
    dispatcher.add_subscriber(Subscriber())


def _remove_listener(dispatcher: CompiledEventDispatcher) -> None:
    dispatcher.remove_listener("foo", _listener)


def _remove_subscriber(dispatcher: CompiledEventDispatcher) -> None:
    dispatcher.remove_subscriber(Subscriber())


@pytest.mark.parametrize(
    ("method", "change"),
    [
        ("add_listener", _add_listener),
        ("add_subscriber", _add_subscriber),
        ("remove_listener", _remove_listener),
        ("remove_subscriber", _remove_subscriber),
    ],
)
def test_every_change_is_refused(
    method: str,
    change: Callable[[CompiledEventDispatcher], object],
) -> None:
    dispatcher = CompiledEventDispatcher({"foo": [(_listener, 0)]})

    with pytest.raises(BadMethodCallError) as raised:
        _ = change(dispatcher)

    assert raised.value.method == method
    assert dispatcher.get_listeners() == {"foo": [_listener]}
