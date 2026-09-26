"""A dispatcher, or its configuration, was given an argument it cannot work with."""

from __future__ import annotations

from .event_dispatcher_error import EventDispatcherError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(EventDispatcherError, ValueError):
    """A dispatcher, or its configuration, was given an argument it cannot work with.

    Also a :class:`ValueError`, so code already guarding its configuration
    with ``except ValueError`` keeps working.

    Attributes:
        reason: What is wrong with the argument.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the argument."""
        self.reason = reason
        super().__init__(reason)
