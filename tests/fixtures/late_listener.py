"""A listener a bundle tags from its own ``process`` hook.

The bundle requires the event dispatcher bundle, as any bundle registering
listeners does, so it is ordered — and processes — after it.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    NoConfig,
    ServiceConfigurator,
    as_bundle,
    required_bundle,
)

from tests.fixtures.app_events.events import OrderPlaced
from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher.bundle import LISTENER_TAG, EventDispatcherBundle


@final
class LateListener:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    def on_placed(self, event: OrderPlaced) -> None:
        self.journal.entries.append(f"late {event.order_id}")


@final
@required_bundle(EventDispatcherBundle)
@as_bundle("late_listener")
class LateListenerBundle(Bundle[NoConfig]):
    @override
    def load_extension(
        self,
        config: NoConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config, builder
        _ = services.set(LateListener)

    @override
    def process(self, builder: ContainerBuilder) -> None:
        _ = builder.get_definition(LateListener).add_tag(
            LISTENER_TAG, event=OrderPlaced, method="on_placed"
        )
