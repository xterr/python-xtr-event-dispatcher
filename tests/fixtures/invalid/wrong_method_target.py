from __future__ import annotations

from xtr_event_dispatcher import Event, as_event_listener


class Stock:
    @as_event_listener("order.placed")
    def on_placed(self, event: Event) -> None:
        del event

    def restock(self) -> None: ...


@as_event_listener("order.placed", after=Stock.restock)
def audit() -> None: ...
