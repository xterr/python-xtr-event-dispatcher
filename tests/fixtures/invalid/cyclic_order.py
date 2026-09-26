from __future__ import annotations

from xtr_event_dispatcher import as_event_listener


@as_event_listener("order.placed", before="tests.fixtures.invalid.cyclic_order:second")
def first() -> None: ...


@as_event_listener("order.placed", before=first)
def second() -> None: ...
