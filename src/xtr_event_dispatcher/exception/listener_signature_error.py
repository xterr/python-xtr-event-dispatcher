"""A callable cannot be called the way a dispatcher calls a listener."""

from __future__ import annotations

from .event_dispatcher_error import EventDispatcherError

__all__ = ["ListenerSignatureError"]


class ListenerSignatureError(EventDispatcherError, TypeError):
    """A callable cannot be called with an event, its name and the dispatcher.

    A dispatcher passes at most those three arguments, by position, so a
    listener may take up to three positional parameters and requires nothing
    else. Raised when the listener is added — or, for a lazy one, when it is
    first built — rather than when the event it waits for arrives.

    Attributes:
        listener: The listener's qualified name.
        signature: Its parameters, as written.
    """

    listener: str
    signature: str

    def __init__(self, listener: str, signature: str) -> None:
        """Record which listener cannot be called, and its parameters."""
        self.listener = listener
        self.signature = signature
        super().__init__(
            f"{listener}{signature} cannot be a listener: it is called with at most the event, "
            f"its name and the dispatcher, by position, so it must require nothing else.",
        )
