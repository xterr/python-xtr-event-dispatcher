from __future__ import annotations

from dataclasses import dataclass

from xtr_event_dispatcher import Event


@dataclass(frozen=True)
class OrderPlaced(Event):
    order_id: int


@dataclass(frozen=True)
class OrderShipped(Event):
    order_id: int
