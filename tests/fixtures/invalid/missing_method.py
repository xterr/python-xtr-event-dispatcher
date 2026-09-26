from __future__ import annotations

from xtr_event_dispatcher import as_event_listener


@as_event_listener("order.placed", method="absent")
class Listener:
    def present(self) -> None: ...
