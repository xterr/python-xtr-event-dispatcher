"""Hands every dispatcher the listeners declared for it, in the order they run."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import final

from xtr_dependency_injection import ContainerBuilder
from xtr_event_dispatcher_contracts import EventDispatcherInterface as DispatcherContract
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

from xtr_event_dispatcher.decorator.event_listener_declaration import EventListenerDeclaration
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface
from xtr_event_dispatcher.exception import InvalidArgumentError, InvalidListenerError

from ._declared_listeners import DISPATCHER_TAG, DeclaredListener, declared_listeners
from ._listener_ordering import ordered
from .event_dispatcher_config import EventDispatcherConfig
from .listener_map import ListenerMap

__all__ = ["RegisterListenersPass"]


@final
class RegisterListenersPass:
    """Gives every dispatcher its listeners, ordered by priority and ``before``/``after``.

    A dispatcher is a service tagged ``event_dispatcher.dispatcher`` — the
    bundle's own, and any another bundle registers. The pass reads the
    services tagged ``event_dispatcher.listener`` and
    ``event_dispatcher.subscriber`` and the functions carrying
    ``@as_event_listener``, checks each — its event, its method, its
    dispatcher, its ordering — and sets every dispatcher's
    :class:`ListenerMap`. It also makes each dispatcher reachable by name
    under the contract's ``EventDispatcherInterface`` and
    ``ListenerIntrospectionInterface``. A mistake fails the build rather than
    the first event.

    :class:`~xtr_event_dispatcher.bundle.EventDispatcherBundle` registers it
    behind every bundle's ``process`` hook, so a listener another bundle tags
    there is registered too.
    """

    __slots__ = ("_functions",)

    def __init__(
        self, functions: Sequence[tuple[Callable[..., object], EventListenerDeclaration]]
    ) -> None:
        """Read function listeners from ``functions``, which the scan fills before the pass runs."""
        self._functions = functions

    def process(self, builder: ContainerBuilder) -> None:
        """Set the listener map of every tagged dispatcher.

        Raises:
            InvalidArgumentError: When a service tagged as a dispatcher is not
                registered as ``EventDispatcherInterface``.
            InvalidListenerError: When a listener cannot be registered, or
                listens on a dispatcher that does not exist.
            InvalidSubscriberError: When a subscriber's declaration cannot be
                read.
        """
        config = builder.get_extension_config(EventDispatcherConfig)
        by_dispatcher: dict[str | None, dict[str, list[DeclaredListener]]] = {
            name: {} for name in _dispatchers(builder)
        }
        for listener in declared_listeners(builder, self._functions, config.aliases()):
            events = by_dispatcher.get(listener.dispatcher)
            if events is None:
                raise InvalidListenerError(
                    listener.label,
                    f"it listens on the dispatcher {listener.dispatcher!r}, which does not "
                    f"exist: add it to EventDispatcherConfig.dispatchers, or register one "
                    f'tagged "{DISPATCHER_TAG}"',
                )
            events.setdefault(listener.event_name, []).append(listener)

        for name, events in by_dispatcher.items():
            listeners = ListenerMap(
                {event: ordered(event, group) for event, group in events.items()}
            )
            _ = builder.get_definition(EventDispatcherInterface, name).set_argument(
                "listeners", listeners
            )
            for alias in (DispatcherContract, ListenerIntrospectionInterface):
                if not builder.has(alias, name):
                    builder.set_alias(
                        alias, EventDispatcherInterface, alias_qualifier=name, target_qualifier=name
                    )


def _dispatchers(builder: ContainerBuilder) -> list[str | None]:
    """Return the name of every tagged dispatcher, refusing one registered under another type."""
    names: list[str | None] = []
    for service, name in builder.find_tagged_service_ids(DISPATCHER_TAG):
        if service is not EventDispatcherInterface or not (name is None or isinstance(name, str)):
            raise InvalidArgumentError(
                f'{service.__qualname__}[{name!r}] is tagged "{DISPATCHER_TAG}", but a dispatcher '
                f"is registered as EventDispatcherInterface under its name: register it with "
                f"event_dispatcher_factory",
            )
        names.append(name)

    return names
