"""Reading what a subscriber declares into one record per listener.

``get_subscribed_events()`` is written by hand and read at runtime, so its
value is parsed here once, whatever its shape, into
:class:`SubscribedListenerDeclaration` records a dispatcher — or a container,
which also needs to know whether a priority was declared at all — can use as
they are.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from xtr_event_dispatcher_contracts import event_name_of

from ._ordering import describe_invalid_target, ordering_targets
from .exception import InvalidSubscriberError

if TYPE_CHECKING:
    from .event_subscriber_interface import EventSubscriberInterface
    from .subscribed_listener import OrderTarget

__all__ = ["SubscribedListenerDeclaration", "bind", "listeners_subscribed_by"]

_KEYS = frozenset({"method", "priority", "before", "after"})


@dataclass(frozen=True, slots=True)
class SubscribedListenerDeclaration:
    """One listener a subscriber declares.

    Attributes:
        event_name: The event it listens to.
        method: The subscriber's method to call.
        priority: The priority declared, ``None`` when none was.
        before: Listeners it must run before.
        after: Listeners it must run after.
    """

    event_name: str
    method: str
    priority: int | None
    before: tuple[OrderTarget, ...] = ()
    after: tuple[OrderTarget, ...] = ()


def listeners_subscribed_by(
    subscriber: type[EventSubscriberInterface],
) -> list[SubscribedListenerDeclaration]:
    """Return every listener ``subscriber`` declares, in declaration order.

    Raises:
        InvalidSubscriberError: When ``get_subscribed_events()`` returns no
            mapping, or a declaration has no shape a listener can be read from.
    """
    events = cast("object", subscriber.get_subscribed_events())
    if not isinstance(events, Mapping):
        raise InvalidSubscriberError(
            subscriber.__qualname__,
            None,
            f"it returns {events!r}, not a mapping of events to the listeners declared for each",
        )

    declared: list[SubscribedListenerDeclaration] = []
    for event, spec in cast("Mapping[object, object]", events).items():
        if not isinstance(event, str | type):
            raise InvalidSubscriberError(
                subscriber.__qualname__,
                None,
                f"{event!r} is neither an event name nor an event class",
            )
        reader = _Reader(subscriber.__qualname__, event_name_of(event))
        items: object = spec
        if isinstance(items, list):
            declared.extend(reader.one(item) for item in cast("list[object]", items))
        else:
            declared.append(reader.one(items))

    return declared


@dataclass(frozen=True, slots=True)
class _Reader:
    """Reads the declarations for one event, naming it and the subscriber in every error."""

    subscriber: str
    event_name: str

    def one(self, item: object) -> SubscribedListenerDeclaration:
        match item:
            case str() as method:
                return SubscribedListenerDeclaration(self.event_name, method, None)
            case (str() as method, int() as priority) if isinstance(item, tuple):
                return SubscribedListenerDeclaration(self.event_name, method, priority)
            case Mapping():
                return self._named(cast("Mapping[object, object]", item))
            case _:
                raise self._error(
                    f"{item!r} declares no listener: give a method name, a (method, priority) "
                    f'pair, a mapping with a "method" key, or a list of those',
                )

    def _named(self, item: Mapping[object, object]) -> SubscribedListenerDeclaration:
        unknown = set(item) - _KEYS
        if unknown:
            raise self._error(f"unknown keys {sorted(map(repr, unknown))} in {item!r}")

        method = item.get("method")
        if not isinstance(method, str):
            raise self._error(f'{item!r} needs a "method" naming the method to call')

        priority = item.get("priority")
        if priority is not None and not isinstance(priority, int):
            raise self._error(f'the "priority" of {method!r} must be an integer, got {priority!r}')

        return SubscribedListenerDeclaration(
            self.event_name,
            method,
            priority,
            self._targets(method, item.get("before")),
            self._targets(method, item.get("after")),
        )

    def _targets(self, method: str, value: object) -> tuple[OrderTarget, ...]:
        return ordering_targets(
            value,
            lambda target: self._error(f"{method!r}: {describe_invalid_target(target)}"),
        )

    def _error(self, reason: str) -> InvalidSubscriberError:
        return InvalidSubscriberError(self.subscriber, self.event_name, reason)


def bind(
    subscriber: EventSubscriberInterface,
    declared: SubscribedListenerDeclaration,
) -> Callable[..., object]:
    """Return the subscriber's declared method as a listener.

    Raises:
        InvalidSubscriberError: When the subscriber has no such method.
    """
    listener: object = getattr(subscriber, declared.method, None)
    if not callable(listener):
        raise InvalidSubscriberError(
            type(subscriber).__qualname__,
            declared.event_name,
            f"it declares the method {declared.method!r}, which it does not have",
        )

    return listener
