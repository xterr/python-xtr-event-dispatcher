"""An event carrying a subject and named arguments, without a class of its own."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from typing import Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

from .exception import ArgumentNotFoundError

__all__ = ["GenericEvent"]


class GenericEvent(Event, MutableMapping[str, object]):  # noqa: PLW1641 — defining __eq__ leaves it unhashable, as a mutable event should be
    """An event about a subject, with arguments read and written like a mapping.

    For an event not worth a class of its own: the subject is what the event
    is about, and the arguments are whatever the dispatcher and its listeners
    exchange.

    ```python
    event = GenericEvent(order, {"notify": True})
    await dispatcher.dispatch(event, "order.saved")
    if event["notify"]:
        ...
    ```

    Two generic events are equal when their subject, arguments and stopped
    state are; being mutable, one cannot be hashed.
    """

    _subject: object
    _arguments: dict[str, object]

    def __init__(
        self, subject: object = None, arguments: Mapping[str, object] | None = None
    ) -> None:
        """Hold the subject, and a copy of the arguments.

        Args:
            subject: What the event is about, usually an object or a callable.
            arguments: The event's initial arguments.
        """
        self._subject = subject
        self._arguments = dict(arguments or {})

    def get_subject(self) -> object:
        """Return what the event is about."""
        return self._subject

    def get_argument(self, key: str) -> object:
        """Return the argument named ``key``.

        Raises:
            ArgumentNotFoundError: When the event has no such argument.
        """
        if key not in self._arguments:
            raise ArgumentNotFoundError(key)

        return self._arguments[key]

    def set_argument(self, key: str, value: object) -> Self:
        """Set the argument named ``key``, and return the event."""
        self._arguments[key] = value
        return self

    def get_arguments(self) -> dict[str, object]:
        """Return a copy of every argument."""
        return dict(self._arguments)

    def set_arguments(self, arguments: Mapping[str, object] | None = None) -> Self:
        """Replace every argument with a copy of ``arguments``, and return the event."""
        self._arguments = dict(arguments or {})
        return self

    def has_argument(self, key: str) -> bool:
        """Tell whether the event has an argument named ``key``."""
        return key in self._arguments

    @override
    def __getitem__(self, key: str) -> object:
        """Return the argument named ``key``; see :meth:`get_argument`."""
        return self.get_argument(key)

    @override
    def __setitem__(self, key: str, value: object) -> None:
        """Set the argument named ``key``."""
        _ = self.set_argument(key, value)

    @override
    def __delitem__(self, key: str) -> None:
        """Remove the argument named ``key``.

        Raises:
            ArgumentNotFoundError: When the event has no such argument.
        """
        if key not in self._arguments:
            raise ArgumentNotFoundError(key)

        del self._arguments[key]

    @override
    def __contains__(self, key: object) -> bool:
        """Tell whether the event has an argument named ``key``."""
        return key in self._arguments

    @override
    def __iter__(self) -> Iterator[str]:
        """Iterate over the argument names."""
        return iter(self._arguments)

    @override
    def __len__(self) -> int:
        """Return how many arguments the event has."""
        return len(self._arguments)

    @override
    def __eq__(self, other: object) -> bool:
        """Compare subject, arguments and stopped state, not only the arguments a mapping would."""
        if not isinstance(other, GenericEvent):
            return NotImplemented

        return (
            self._subject == other._subject
            and self._arguments == other._arguments
            and self.is_propagation_stopped() == other.is_propagation_stopped()
        )

    @override
    def __repr__(self) -> str:
        """Show the subject and the arguments."""
        return f"GenericEvent({self._subject!r}, {self._arguments!r})"
