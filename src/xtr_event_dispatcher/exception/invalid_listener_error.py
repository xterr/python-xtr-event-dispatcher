"""A declared listener cannot be registered as it stands."""

from __future__ import annotations

from .event_dispatcher_error import EventDispatcherError

__all__ = ["InvalidListenerError"]


class InvalidListenerError(EventDispatcherError, ValueError):
    """A listener declared with ``@as_event_listener``, or tagged by hand, cannot be registered.

    Raised while the container is built, never on the first event: an event
    that cannot be told from the listener's signature, a method the class
    does not have, a dispatcher nobody configured, ordering constraints that
    contradict each other.

    Attributes:
        listener: The listener, as ``"module:Qualified.name"``.
        reason: What is wrong with it.
    """

    listener: str
    reason: str

    def __init__(self, listener: str, reason: str) -> None:
        """Record which listener is wrong, and why."""
        self.listener = listener
        self.reason = reason
        super().__init__(f"Listener {listener}: {reason}")
