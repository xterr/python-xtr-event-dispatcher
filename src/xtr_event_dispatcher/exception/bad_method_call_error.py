"""A dispatcher was asked to change, and it cannot be changed."""

from __future__ import annotations

from .event_dispatcher_error import EventDispatcherError

__all__ = ["BadMethodCallError"]


class BadMethodCallError(EventDispatcherError, RuntimeError):
    """A dispatcher was asked to add or remove a listener, and it cannot be changed.

    Raised by
    :class:`~xtr_event_dispatcher.immutable_event_dispatcher.ImmutableEventDispatcher`,
    which hands its dispatcher out for dispatching only. A listener that
    must live for a while only belongs on a
    :class:`~xtr_event_dispatcher.scoped_event_dispatcher.ScopedEventDispatcher`
    wrapping it.

    Attributes:
        method: The method that was called.
    """

    method: str

    def __init__(self, method: str) -> None:
        """Record which method was called."""
        self.method = method
        super().__init__(
            f"{method}() cannot be called: this event dispatcher cannot be modified; "
            f"add the listener to a ScopedEventDispatcher wrapping it instead.",
        )
