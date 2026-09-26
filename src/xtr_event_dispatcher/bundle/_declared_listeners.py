"""Reading every listener the container knows of into one record each.

Listeners come three ways: services tagged ``event_dispatcher.listener`` —
what ``@as_event_listener`` on a class or a method becomes — services tagged
``event_dispatcher.subscriber``, and functions carrying ``@as_event_listener``.
Each is read here into a :class:`DeclaredListener`, its event worked out
from its signature when not given, and its method checked, so a mistake fails
the build rather than the first event.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from xtr_dependency_injection import ContainerBuilder
from xtr_event_dispatcher_contracts import event_name_of

from xtr_event_dispatcher._ordering import describe_invalid_target, ordering_targets, target_name
from xtr_event_dispatcher._subscribed_events import listeners_subscribed_by
from xtr_event_dispatcher.decorator.event_listener_declaration import EventListenerDeclaration
from xtr_event_dispatcher.event_subscriber_interface import EventSubscriberInterface
from xtr_event_dispatcher.exception import InvalidListenerError

from ._listener_reference import FunctionListener, ListenerReference, ServiceListener
from ._listener_signature import (
    CALL,
    check_method,
    default_method,
    events_of,
    function_of,
    function_of_or_none,
    own_arity,
)

__all__ = ["LISTENER_TAG", "SUBSCRIBER_TAG", "DeclaredListener", "declared_listeners"]

LISTENER_TAG = "event_dispatcher.listener"
SUBSCRIBER_TAG = "event_dispatcher.subscriber"

_TAG_KEYS = frozenset({"event", "method", "priority", "dispatcher", "before", "after"})


@dataclass(frozen=True, slots=True)
class DeclaredListener:
    """One listener of one event on one dispatcher, before ordering.

    Attributes:
        reference: How to reach it once the container runs.
        event_name: The event, aliases applied.
        priority: The priority declared, ``None`` when none was.
        dispatcher: The named dispatcher, ``None`` for the default one.
        before: Names of listeners it runs before.
        after: Names of listeners it runs after.
        names: Every ``"module:Qualified.name"`` designating it: its class
            and its method, or its function.
    """

    reference: ListenerReference
    event_name: str
    priority: int | None
    dispatcher: str | None
    before: tuple[str, ...]
    after: tuple[str, ...]
    names: tuple[str, ...]

    @property
    def label(self) -> str:
        """The most precise of its names, for errors."""
        return self.names[-1]


def declared_listeners(
    builder: ContainerBuilder,
    functions: list[tuple[Callable[..., object], EventListenerDeclaration]],
    aliases: dict[str, str],
) -> list[DeclaredListener]:
    """Return every listener, in declaration order: tagged services, subscribers, functions.

    Raises:
        InvalidListenerError: When a listener cannot be registered.
        InvalidSubscriberError: When a subscriber's declaration cannot be read.
    """
    declared: list[DeclaredListener] = []
    for key, tags in builder.find_tagged_service_ids(LISTENER_TAG).items():
        owner = _class_of(builder, key)
        for attributes in tags:
            declaration = _declaration_from(attributes, target_name(owner))
            declared.extend(_class_listeners(key, owner, declaration, aliases))

    for key, tags in builder.find_tagged_service_ids(SUBSCRIBER_TAG).items():
        declared.extend(_subscriber_listeners(key, _class_of(builder, key), tags, aliases))

    for function, declaration in functions:
        declared.extend(_function_listeners(function, declaration, aliases))

    return declared


def _class_of(builder: ContainerBuilder, key: tuple[type, Hashable | None]) -> type:
    """Return the class a listener service is built as, refusing one the dispatcher cannot keep.

    The dispatcher fetches a listener once and keeps it, so it must be a
    singleton; any other lifetime would fail on the first event.
    """
    definition = builder.find_definition(*key)
    owner = definition.provider if isinstance(definition.provider, type) else key[0]
    if definition.lifetime != "singleton":
        raise InvalidListenerError(
            target_name(owner),
            f'it is registered "{definition.lifetime}", but a listener service must be a '
            f"singleton: the dispatcher keeps it once built",
        )

    return owner


def _declaration_from(attributes: dict[str, object], label: str) -> EventListenerDeclaration:
    """Read a tag's attributes, which a bundle may have written by hand."""

    def invalid(reason: str) -> InvalidListenerError:
        return InvalidListenerError(label, f'its "{LISTENER_TAG}" tag {reason}')

    unknown = set(attributes) - _TAG_KEYS
    if unknown:
        raise invalid(f"has unknown attributes {sorted(unknown)}")

    event = attributes.get("event")
    method = attributes.get("method")
    priority = attributes.get("priority")
    dispatcher = attributes.get("dispatcher")
    if not (event is None or isinstance(event, str | type)):
        raise invalid(f"names the event {event!r}, which is neither a name nor a class")
    if not (method is None or isinstance(method, str)):
        raise invalid(f"names the method {method!r}, which is not a name")
    if not (priority is None or isinstance(priority, int)):
        raise invalid(f"gives the priority {priority!r}, which is not an integer")
    if not (dispatcher is None or isinstance(dispatcher, str)):
        raise invalid(f"names the dispatcher {dispatcher!r}, which is not a name")

    def invalid_target(target: object) -> InvalidListenerError:
        return InvalidListenerError(label, describe_invalid_target(target))

    return EventListenerDeclaration(
        event,
        method,
        priority,
        dispatcher,
        ordering_targets(attributes.get("before"), invalid_target),
        ordering_targets(attributes.get("after"), invalid_target),
    )


def _class_listeners(
    key: tuple[type, Hashable | None],
    owner: type,
    declaration: EventListenerDeclaration,
    aliases: dict[str, str],
) -> list[DeclaredListener]:
    events: list[str | type]
    method = declaration.method
    if declaration.event is None:
        # The event is read from the method's signature, so that method is the one called.
        method = method or CALL
        function, bound = function_of(owner, method)
        events = events_of(function, target_name(owner), skip_first=bound)
    else:
        events = [declaration.event]

    declared: list[DeclaredListener] = []
    for event in events:
        called = method or default_method(owner, event)
        names = _names(owner, called)
        check_method(owner, called, names[-1])
        declared.append(
            DeclaredListener(
                ServiceListener(key[0], key[1], called),
                _alias(event, aliases),
                declaration.priority,
                declaration.dispatcher,
                tuple(map(target_name, declaration.before)),
                tuple(map(target_name, declaration.after)),
                names,
            ),
        )

    return declared


def _subscriber_listeners(
    key: tuple[type, Hashable | None],
    owner: type,
    tags: list[dict[str, object]],
    aliases: dict[str, str],
) -> list[DeclaredListener]:
    label = target_name(owner)
    if not issubclass(owner, EventSubscriberInterface):
        raise InvalidListenerError(
            label,
            f'it is tagged "{SUBSCRIBER_TAG}" but does not derive from EventSubscriberInterface',
        )

    dispatchers: list[str | None] = []
    for attributes in tags:
        dispatcher = attributes.get("dispatcher")
        if not (dispatcher is None or isinstance(dispatcher, str)):
            raise InvalidListenerError(
                target_name(owner),
                f"its subscriber tag names the dispatcher {dispatcher!r}, which is not a name",
            )
        if dispatcher not in dispatchers:
            dispatchers.append(dispatcher)

    declared: list[DeclaredListener] = []
    for subscribed in listeners_subscribed_by(owner):
        names = _names(owner, subscribed.method)
        check_method(owner, subscribed.method, names[-1])
        declared.extend(
            DeclaredListener(
                ServiceListener(key[0], key[1], subscribed.method),
                aliases.get(subscribed.event_name, subscribed.event_name),
                subscribed.priority,
                dispatcher,
                tuple(map(target_name, subscribed.before)),
                tuple(map(target_name, subscribed.after)),
                names,
            )
            for dispatcher in dispatchers or [None]
        )

    return declared


def _function_listeners(
    function: Callable[..., object],
    declaration: EventListenerDeclaration,
    aliases: dict[str, str],
) -> list[DeclaredListener]:
    label = target_name(function)
    if declaration.method is not None:
        raise InvalidListenerError(label, "a function has no method to name")

    events = [declaration.event] if declaration.event is not None else events_of(function, label)
    reference = FunctionListener(function, own_arity(function, label))

    return [
        DeclaredListener(
            reference,
            _alias(event, aliases),
            declaration.priority,
            declaration.dispatcher,
            tuple(map(target_name, declaration.before)),
            tuple(map(target_name, declaration.after)),
            (label,),
        )
        for event in events
    ]


def _names(owner: type, method: str) -> tuple[str, ...]:
    """Return what designates a class's listener: the class, then its method.

    A method inherited from a base class is also named after that base —
    ``Stock.reserve`` evaluates to the function defined on ``Base`` — so
    ordering against it finds this listener either way. The class and method
    come last, as the label.
    """
    label = f"{target_name(owner)}.{method}"
    found = function_of_or_none(owner, method)
    defined = target_name(found[0]) if found is not None else label

    return (target_name(owner), *dict.fromkeys((defined, label)))


def _alias(event: str | type, aliases: dict[str, str]) -> str:
    name = event_name_of(event)
    return aliases.get(name, name)
