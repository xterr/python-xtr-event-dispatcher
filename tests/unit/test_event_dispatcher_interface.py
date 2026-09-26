from __future__ import annotations

import xtr_event_dispatcher_contracts

from xtr_event_dispatcher import (
    EventDispatcher,
    EventDispatcherInterface,
    ImmutableEventDispatcher,
    ScopedEventDispatcher,
)


def test_every_dispatcher_here_registers_listeners() -> None:
    inner = EventDispatcher()

    for dispatcher in (inner, ImmutableEventDispatcher(inner), ScopedEventDispatcher(inner)):
        assert isinstance(dispatcher, EventDispatcherInterface)


def test_a_dispatcher_here_fulfils_both_contracts() -> None:
    dispatcher = EventDispatcher()

    assert isinstance(dispatcher, xtr_event_dispatcher_contracts.EventDispatcherInterface)
    assert isinstance(dispatcher, xtr_event_dispatcher_contracts.ListenerIntrospectionInterface)


def test_a_dispatcher_that_only_dispatches_cannot_register_listeners() -> None:
    class _OnlyDispatches:
        async def dispatch(self, event: object, event_name: str | type | None = None) -> object:
            del event_name
            return event

    assert not isinstance(_OnlyDispatches(), EventDispatcherInterface)
