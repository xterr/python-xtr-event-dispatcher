"""A dispatcher that listeners are registered on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xtr_event_dispatcher_contracts import EventDispatcherInterface as DispatcherContract
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

    from .event_subscriber_interface import EventSubscriberInterface

__all__ = ["EventDispatcherInterface"]


@runtime_checkable
class EventDispatcherInterface(DispatcherContract, ListenerIntrospectionInterface, Protocol):
    """The whole dispatcher: dispatching, reading its listeners, and changing them.

    Whoever builds a dispatcher registers listeners through this; code that
    only dispatches should depend on the contract's narrower
    ``EventDispatcherInterface`` instead. Wherever an event name is taken, a
    class stands for its name.
    """

    def add_listener(self, event_name: str | type, listener: Listener, priority: int = 0) -> None:
        """Run ``listener`` whenever the event is dispatched.

        Args:
            event_name: The event to listen to.
            listener: What to call — see
                :data:`~xtr_event_dispatcher_contracts.listener.Listener`.
            priority: Higher runs earlier; listeners sharing a priority run in
                the order they were added.

        Raises:
            ListenerSignatureError: When ``listener`` cannot be called the way
                a dispatcher calls listeners.
        """
        ...

    def add_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Add a listener for every method ``subscriber`` declares.

        Raises:
            InvalidSubscriberError: When a declaration cannot be registered.
        """
        ...

    def remove_listener(self, event_name: str | type, listener: Listener) -> None:
        """Stop running ``listener`` for the event; one that was not registered is ignored."""
        ...

    def remove_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Remove every listener :meth:`add_subscriber` added for ``subscriber``."""
        ...
