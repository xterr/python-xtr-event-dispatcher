"""What a traceable dispatcher reports about one listener of one event."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ListenerInfo"]


@dataclass(frozen=True, slots=True)
class ListenerInfo:
    """One listener of one event, as a debugging tool shows it.

    Attributes:
        event: The event the listener listens to.
        priority: The priority it runs at, ``None`` when the dispatcher
            cannot tell.
        pretty: A readable name — ``"app.mail.Mailer.on_placed"``, a
            function's qualified name.
        calls: How many times it ran since the last reset; ``0`` for one
            that never did.
    """

    event: str
    priority: int | None
    pretty: str
    calls: int = 0
