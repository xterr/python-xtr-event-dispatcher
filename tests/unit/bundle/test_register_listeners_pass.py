"""The pass hands every dispatcher its listeners once every bundle has had its say."""

from __future__ import annotations

import pytest
import xtr_event_dispatcher_contracts
from xtr_dependency_injection import Bundle, Kernel, NoConfig

from tests.fixtures.app_events.events import OrderPlaced
from tests.fixtures.app_events.journal import Journal
from tests.fixtures.late_listener import LateListenerBundle
from tests.fixtures.owned_dispatcher import (
    OWNED,
    MistaggedDispatcherBundle,
    OwnedDispatcherBundle,
)
from xtr_event_dispatcher import Event, EventDispatcherInterface, InvalidArgumentError
from xtr_event_dispatcher.bundle import EventDispatcherBundle

pytestmark = pytest.mark.anyio


def _kernel(bundle: type[Bundle[NoConfig]]) -> Kernel:
    return Kernel(
        "tests.fixtures.app_events",
        env="test",
        debug=False,
        bundles={EventDispatcherBundle: {"all": True}, bundle: {"all": True}},
    )


async def test_a_listener_another_bundle_tags_while_processing_is_registered() -> None:
    async with await _kernel(LateListenerBundle).boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)
        _ = await dispatcher.dispatch(OrderPlaced(42))

    assert "late 42" in journal.entries


async def test_a_dispatcher_another_bundle_tags_gets_the_listeners_naming_it() -> None:
    async with await _kernel(OwnedDispatcherBundle).boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface, OWNED)
        journal = await booted.container.get(Journal)
        _ = await dispatcher.dispatch(Event(), "order.audited")

    assert journal.entries == ["audited on the owned dispatcher"]


async def test_a_dispatcher_another_bundle_tags_is_reachable_through_the_contracts() -> None:
    async with await _kernel(OwnedDispatcherBundle).boot() as booted:
        contract = await booted.container.get(
            xtr_event_dispatcher_contracts.EventDispatcherInterface, OWNED
        )
        introspection = await booted.container.get(
            xtr_event_dispatcher_contracts.ListenerIntrospectionInterface, OWNED
        )

    assert contract is introspection
    assert introspection.has_listeners("order.audited")


async def test_a_service_tagged_as_a_dispatcher_but_registered_otherwise_fails_the_build() -> None:
    with pytest.raises(InvalidArgumentError, match="NotADispatcher"):
        _ = _kernel(MistaggedDispatcherBundle).build()
