"""A subscriber declares its events in a way no dispatcher can read."""

from __future__ import annotations

from .event_dispatcher_error import EventDispatcherError

__all__ = ["InvalidSubscriberError"]


class InvalidSubscriberError(EventDispatcherError, ValueError):
    """A subscriber's ``get_subscribed_events()`` cannot be registered as it stands.

    Raised when the subscriber is added, before any of its listeners is:
    a declaration of an unknown shape, a method the subscriber does not have,
    or ordering constraints a dispatcher on its own cannot honour.

    Attributes:
        subscriber: The subscriber's qualified class name.
        event_name: The event whose declaration is wrong; ``None`` when
            what is wrong is not about one event.
        reason: What is wrong with it.
    """

    subscriber: str
    event_name: str | None
    reason: str

    def __init__(self, subscriber: str, event_name: str | None, reason: str) -> None:
        """Record which declaration is wrong, and why."""
        self.subscriber = subscriber
        self.event_name = event_name
        self.reason = reason
        where = "" if event_name is None else f' for event "{event_name}"'
        super().__init__(f"{subscriber}.get_subscribed_events(){where}: {reason}")
