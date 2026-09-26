"""What ``@as_event_listener`` records, and reading it back."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

from xtr_event_dispatcher._ordering import target_name
from xtr_event_dispatcher.exception import InvalidListenerError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_event_dispatcher.subscribed_listener import OrderTarget

__all__ = [
    "LISTENERS_ATTRIBUTE",
    "EventListenerDeclaration",
    "listeners_declared_on",
    "recorded_on",
]

LISTENERS_ATTRIBUTE = "__xtr_event_dispatcher_listeners__"
"""Where :func:`~xtr_event_dispatcher.decorator.as_event_listener.as_event_listener` records."""


@dataclass(frozen=True, slots=True)
class EventListenerDeclaration:
    """One ``@as_event_listener`` on a class, a method or a function.

    Attributes:
        event: The event listened to; ``None`` reads it from the type of the
            listener's first parameter.
        method: The method to call; ``None`` on a class picks
            ``on_<event>`` or ``__call__``, and on a function calls it.
        priority: The priority declared, ``None`` when none was.
        dispatcher: The named dispatcher to listen on; ``None`` for the
            default one.
        before: Listeners this one must run before.
        after: Listeners this one must run after.
    """

    event: str | type | None = None
    method: str | None = None
    priority: int | None = None
    dispatcher: str | None = None
    before: tuple[OrderTarget, ...] = ()
    after: tuple[OrderTarget, ...] = ()


def listeners_declared_on(obj: object) -> tuple[EventListenerDeclaration, ...]:
    """Return every listener ``@as_event_listener`` declared on ``obj``.

    On a function, its own declarations. On a class, those on the class
    itself, then those on its methods — inherited, static and class methods
    included — each naming the method it sits on.

    Raises:
        InvalidListenerError: When a declaration on a method names a method
            to call: it is the method it sits on.
    """
    if not isinstance(obj, type):
        return recorded_on(obj)

    declared = list(recorded_on(obj))
    seen: set[str] = set()
    for klass in obj.__mro__[:-1]:
        for name, member in _members(klass).items():
            if name in seen:
                continue
            seen.add(name)
            function = (
                cast("object", member.__func__)
                if isinstance(member, staticmethod | classmethod)
                else member
            )
            if inspect.isfunction(function):
                declared.extend(
                    _with_method(declaration, function, name)
                    for declaration in recorded_on(function)
                )

    return tuple(declared)


def recorded_on(obj: object) -> tuple[EventListenerDeclaration, ...]:
    """Return the declarations made on ``obj`` itself, not on its methods.

    A class's own only: a base class's declarations are the base class's
    listeners, and a subclass declares its own.
    """
    recorded = (
        _members(obj).get(LISTENERS_ATTRIBUTE, ())
        if isinstance(obj, type)
        else cast("object", getattr(obj, LISTENERS_ATTRIBUTE, ()))
    )
    return _declarations(recorded)


def _members(klass: type) -> Mapping[str, object]:
    return cast("Mapping[str, object]", vars(klass))


def _declarations(recorded: object) -> tuple[EventListenerDeclaration, ...]:
    if not isinstance(recorded, tuple):
        return ()

    items = cast("tuple[object, ...]", recorded)
    return tuple(item for item in items if isinstance(item, EventListenerDeclaration))


def _with_method(
    declaration: EventListenerDeclaration,
    function: Callable[..., object],
    name: str,
) -> EventListenerDeclaration:
    if declaration.method is not None:
        raise InvalidListenerError(
            target_name(function),
            "@as_event_listener on a method cannot name another method to call",
        )

    return replace(declaration, method=name)
