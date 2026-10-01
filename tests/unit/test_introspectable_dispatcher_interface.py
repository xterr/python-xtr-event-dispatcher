from __future__ import annotations

import pytest

from tests.support.dispatchers import ReadOnlyDispatcher
from xtr_event_dispatcher import (
    EventDispatcher,
    ImmutableEventDispatcher,
    IntrospectableDispatcherInterface,
    ScopedEventDispatcher,
)
from xtr_event_dispatcher.debug import TraceableEventDispatcher


def test_every_dispatcher_here_can_be_wrapped() -> None:
    inner = EventDispatcher()

    for dispatcher in (
        inner,
        ImmutableEventDispatcher(inner),
        ScopedEventDispatcher(inner),
        TraceableEventDispatcher(inner),
    ):
        assert isinstance(dispatcher, IntrospectableDispatcherInterface)


def test_a_dispatcher_that_only_dispatches_cannot_be_wrapped() -> None:
    class _OnlyDispatches:
        async def dispatch(self, event: object, event_name: str | type | None = None) -> object:
            del event_name
            return event

    assert not isinstance(_OnlyDispatches(), IntrospectableDispatcherInterface)


def test_a_dispatcher_written_against_the_contracts_alone_can_be_wrapped() -> None:
    assert isinstance(ReadOnlyDispatcher({}), IntrospectableDispatcherInterface)


@pytest.mark.anyio
async def test_a_dispatcher_written_against_the_contracts_alone_can_be_scoped() -> None:
    heard: list[str] = []

    def shared(_event: object) -> None:
        heard.append("shared")

    def scoped_only(_event: object) -> None:
        heard.append("scoped")

    scoped = ScopedEventDispatcher(ReadOnlyDispatcher({"order.placed": [shared]}))
    scoped.add_listener("order.placed", scoped_only, priority=-1)

    _ = await scoped.dispatch(object(), "order.placed")

    assert heard == ["shared", "scoped"]
