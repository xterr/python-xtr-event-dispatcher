"""Base classes lending listeners to the classes built from them, and not listening themselves."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from typing_extensions import override
from xtr_dependency_injection import Injected, exclude

from tests.fixtures.app_events.journal import Journal
from xtr_event_dispatcher import Event, EventSubscriberInterface, as_event_listener


class AbstractWarehouse(ABC):
    journal: Journal

    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    @abstractmethod
    def region(self) -> str: ...

    @as_event_listener("stock.counted")
    def count(self, _event: Event) -> None:
        self.journal.entries.append(f"counted in {self.region()}")


@final
class EuropeWarehouse(AbstractWarehouse):
    @override
    def region(self) -> str:
        return "europe"


@exclude
class ExcludedBase:
    journal: Journal

    def __init__(self, journal: Journal) -> None:
        self.journal = journal

    @as_event_listener("stock.counted")
    def audit(self, _event: Event) -> None:
        self.journal.entries.append(f"audited by {type(self).__name__}")


@final
class Auditor(ExcludedBase):
    pass


class BaseSubscriber(EventSubscriberInterface, ABC):
    """Leaves ``get_subscribed_events`` to its subclasses, with no abstract method to say so."""


@as_event_listener("stock.%level%")
def level(_event: Event, journal: Injected[Journal]) -> None:
    journal.entries.append("level")
