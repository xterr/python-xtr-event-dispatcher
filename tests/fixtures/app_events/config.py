from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.app_events.events import OrderPlaced
from xtr_event_dispatcher.bundle import EventDispatcherConfig


@configure
def event_dispatcher() -> EventDispatcherConfig:
    return EventDispatcherConfig(
        event_aliases={"legacy.placed": OrderPlaced}, dispatchers=("audit",)
    )
