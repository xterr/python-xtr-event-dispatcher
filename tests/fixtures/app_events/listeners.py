from __future__ import annotations

from collections.abc import Mapping
from typing import final

from typing_extensions import override
from xtr_dependency_injection import Injected

from tests.fixtures.app_events.events import OrderPlaced, OrderShipped
from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher import (
    Event,
    EventSubscriberInterface,
    SubscribedEvents,
    as_event_listener,
)


@final
class Stock:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal
        journal.entries.append("stock built")

    @as_event_listener(priority=10)
    def on_placed(self, event: OrderPlaced) -> None:
        self.journal.entries.append(f"stock {event.order_id}")


@final
@as_event_listener(OrderShipped)
class Shipping:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal
        journal.entries.append("shipping built")

    def on_order_shipped(self, event: OrderShipped, _name: str, dispatcher: object) -> None:
        self.journal.entries.append(f"shipped {event.order_id} via {type(dispatcher).__name__}")


@final
class Mailer(EventSubscriberInterface):
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {OrderPlaced: ("on_placed", -10)}

    def on_placed(self, event: OrderPlaced) -> None:
        self.journal.entries.append(f"mail {event.order_id}")


@as_event_listener()
async def send_receipt(event: OrderPlaced, journal: Injected[Journal]) -> None:
    journal.entries.append(f"receipt {event.order_id}")


@as_event_listener(after=Stock)
def audit(event: OrderPlaced | OrderShipped, journal: Injected[Journal]) -> None:
    journal.entries.append(f"audit {type(event).__name__}")


@as_event_listener("legacy.placed", priority=-5)
def legacy(event: Event, journal: Injected[Journal]) -> None:
    del event
    journal.entries.append("legacy")


@as_event_listener("order.cancelled", dispatcher="audit")
def cancelled(event: Event, name: str, journal: Injected[Journal]) -> None:
    del event
    journal.entries.append(f"cancelled on {name}")
