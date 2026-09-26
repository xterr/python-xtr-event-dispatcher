"""A subscriber a bundle registers by hand, qualified, on the audit dispatcher."""

from __future__ import annotations

from collections.abc import Mapping
from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    NoConfig,
    ServiceConfigurator,
    as_bundle,
)

from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher import Event, EventSubscriberInterface, SubscribedEvents


@final
class QualifiedAudit(EventSubscriberInterface):
    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"order.refunded": "on_refunded"}

    def on_refunded(self, _event: Event) -> None:
        self.journal.entries.append("refund audited")


@final
@as_bundle("qualified_audit")
class QualifiedAuditBundle(Bundle[NoConfig]):
    @override
    def load_extension(
        self,
        config: NoConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        del config, builder
        _ = services.set(QualifiedAudit, qualifier="audit").add_tag(
            "event_dispatcher.subscriber",
            dispatcher="audit",
        )
