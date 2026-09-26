"""A generic event was asked for an argument it does not carry."""

from __future__ import annotations

from typing_extensions import override

from .event_dispatcher_error import EventDispatcherError

__all__ = ["ArgumentNotFoundError"]


class ArgumentNotFoundError(EventDispatcherError, KeyError):
    """A :class:`~xtr_event_dispatcher.generic_event.GenericEvent` has no such argument.

    Also a :class:`KeyError`, since a generic event is read like a mapping:
    ``event["name"]`` raising it is what any mapping would do.

    Attributes:
        key: The argument that was asked for.
    """

    key: str

    def __init__(self, key: str) -> None:
        """Record which argument was asked for."""
        self.key = key
        super().__init__(key)

    @override
    def __str__(self) -> str:
        """Describe the missing argument, rather than quote the key as ``KeyError`` would."""
        return f'Argument "{self.key}" not found.'
