from __future__ import annotations

from xtr_event_dispatcher import Event, as_event_listener


@as_event_listener("order.placed", dispatcher="nowhere")
def listener(event: Event) -> None:
    del event
