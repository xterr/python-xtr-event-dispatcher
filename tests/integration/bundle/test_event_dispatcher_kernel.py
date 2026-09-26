"""The bundle, driven through a real kernel scanning a fixture application."""

from __future__ import annotations

import pytest
import xtr_event_dispatcher_contracts
from xtr_dependency_injection import Kernel
from xtr_logging_contracts import LoggerInterface

from tests.fixtures.app_events.events import OrderPlaced, OrderShipped
from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher import (
    BadMethodCallError,
    CompiledEventDispatcher,
    Event,
    EventDispatcherInterface,
    InvalidListenerError,
    ScopedEventDispatcher,
)
from xtr_event_dispatcher.bundle import EVENT_CHANNEL, EventDispatcherBundle
from xtr_event_dispatcher.debug import TraceableEventDispatcher

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_events"


def _kernel(*, debug: bool = False) -> Kernel:
    return Kernel(APP, env="test", debug=debug)


def _invalid(module: str) -> Kernel:
    return Kernel(
        APP,
        env="test",
        debug=False,
        bundles={EventDispatcherBundle: {"all": True}},
        resources=(f"tests.fixtures.invalid.{module}",),
    )


async def test_declared_listeners_run_by_priority_and_order() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(OrderPlaced(42))

    ran = [entry for entry in journal.entries if not entry.endswith("built")]
    assert ran[0] == "stock 42"
    assert ran[-1] == "mail 42"
    assert set(ran) == {"stock 42", "receipt 42", "audit OrderPlaced", "legacy", "mail 42"}
    assert ran.index("audit OrderPlaced") > ran.index("stock 42")
    assert ran.index("legacy") > ran.index("receipt 42")


async def test_a_listener_service_is_built_only_when_an_event_reaches_it() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(OrderShipped(7))

    assert "shipping built" in journal.entries
    assert "stock built" not in journal.entries


async def test_a_union_annotation_listens_to_each_event() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(OrderShipped(7))

    assert "audit OrderShipped" in journal.entries


async def test_every_interface_is_the_same_dispatcher() -> None:
    async with await _kernel().boot() as booted:
        full = await booted.container.get(EventDispatcherInterface)
        contract = await booted.container.get(
            xtr_event_dispatcher_contracts.EventDispatcherInterface
        )
        introspection = await booted.container.get(
            xtr_event_dispatcher_contracts.ListenerIntrospectionInterface,
        )

    assert full is contract
    assert full is introspection
    assert isinstance(full, CompiledEventDispatcher)


async def test_the_container_dispatcher_refuses_new_listeners() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)

        with pytest.raises(BadMethodCallError):
            dispatcher.add_listener(OrderPlaced, lambda: None)


async def test_a_listener_receives_the_dispatcher_that_cannot_change() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(OrderShipped(7))

    assert "shipped 7 via CompiledEventDispatcher" in journal.entries


async def test_a_scoped_dispatcher_adds_listeners_next_to_the_containers() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)
        scoped = ScopedEventDispatcher(dispatcher)
        scoped.add_listener(OrderPlaced, lambda: journal.entries.append("scoped"))

        _ = await scoped.dispatch(OrderPlaced(1))

    assert "scoped" in journal.entries
    assert "stock 1" in journal.entries
    assert len(dispatcher.get_listeners(OrderPlaced)) == 5


async def test_a_named_dispatcher_holds_its_own_listeners() -> None:
    async with await _kernel().boot() as booted:
        audit = await booted.container.get(EventDispatcherInterface, "audit")
        default = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await audit.dispatch(Event(), "order.cancelled")

    assert journal.entries == ["cancelled on order.cancelled"]
    assert not default.has_listeners("order.cancelled")


async def test_in_debug_the_dispatcher_is_traced_to_the_event_channel() -> None:
    async with await _kernel(debug=True).boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(OrderShipped(7))
        _ = await dispatcher.dispatch(Event(), "nobody.listens")

        assert booted.container.has(LoggerInterface, EVENT_CHANNEL)

    assert isinstance(dispatcher, TraceableEventDispatcher)
    assert "shipped 7 via TraceableEventDispatcher" in journal.entries
    assert dispatcher.get_orphaned_events() == ["nobody.listens"]
    assert {info.pretty for info in dispatcher.get_called_listeners()} == {
        "tests.fixtures.app_events.listeners.Shipping.on_order_shipped",
        "tests.fixtures.app_events.listeners.audit",
    }


async def test_an_abstract_or_excluded_base_lends_its_listeners_without_listening() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(Event(), "stock.counted")

    assert sorted(journal.entries) == ["audited by Auditor", "counted in europe"]


async def test_an_event_name_is_not_read_as_a_parameter() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)
        journal = await booted.container.get(Journal)

        _ = await dispatcher.dispatch(Event(), "stock.%level%")

    assert journal.entries == ["level"]


async def test_a_qualified_subscriber_listens_on_the_dispatcher_its_tag_names() -> None:
    async with await _kernel().boot() as booted:
        audit = await booted.container.get(EventDispatcherInterface, "audit")
        journal = await booted.container.get(Journal)

        _ = await audit.dispatch(Event(), "order.refunded")

    assert journal.entries == ["refund audited"]


async def test_a_listener_not_built_yet_is_named_after_its_service() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)

        listeners = dispatcher.get_listeners(OrderShipped)

    assert "LazyListener(tests.fixtures.app_events.listeners.Shipping, 'on_order_shipped')" in map(
        repr, listeners
    )


async def test_a_listener_declaring_no_event_fails_the_build() -> None:
    with pytest.raises(InvalidListenerError, match="it declares no event"):
        _ = await _invalid("no_event").boot()


async def test_a_listener_on_an_unconfigured_dispatcher_fails_the_build() -> None:
    with pytest.raises(InvalidListenerError, match="'nowhere', which is not configured"):
        _ = await _invalid("unknown_dispatcher").boot()


async def test_a_listener_naming_a_missing_method_fails_the_build() -> None:
    with pytest.raises(InvalidListenerError, match="has no method 'absent'"):
        _ = await _invalid("missing_method").boot()


async def test_constraints_forming_a_cycle_fail_the_build() -> None:
    with pytest.raises(InvalidListenerError, match="cannot be met"):
        _ = await _invalid("cyclic_order").boot()


async def test_ordering_against_a_method_that_does_not_listen_fails_the_build() -> None:
    with pytest.raises(InvalidListenerError, match="does not listen to the event"):
        _ = await _invalid("wrong_method_target").boot()
