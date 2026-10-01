"""A bundle owning a dispatcher of its own, and one tagging a service that is not a dispatcher."""

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

from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher import Event
from xtr_event_dispatcher.bundle import (
    DISPATCHER_TAG,
    LISTENER_TAG,
    EventDispatcherBundle,
    event_dispatcher_factory,
)

OWNED = "owned.event_dispatcher"


@final
class OwnedListener:
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    def on_audited(self, _event: Event) -> None:
        self.journal.entries.append("audited on the owned dispatcher")


@final
@required_bundle(EventDispatcherBundle)
@as_bundle("owned_dispatcher")
class OwnedDispatcherBundle(Bundle[NoConfig]):
    @override
    def load_extension(
        self,
        config: NoConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config, builder
        _ = services.set(event_dispatcher_factory(OWNED), qualifier=OWNED).add_tag(DISPATCHER_TAG)
        _ = services.set(OwnedListener).add_tag(
            LISTENER_TAG, event="order.audited", method="on_audited", dispatcher=OWNED
        )


@final
class NotADispatcher:
    pass


@final
@required_bundle(EventDispatcherBundle)
@as_bundle("mistagged_dispatcher")
class MistaggedDispatcherBundle(Bundle[NoConfig]):
    @override
    def load_extension(
        self,
        config: NoConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config, builder
        _ = services.set(NotADispatcher).add_tag(DISPATCHER_TAG)
