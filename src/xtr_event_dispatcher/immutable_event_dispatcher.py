"""A dispatcher handed out for dispatching only."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, TypeVar, final, overload

from typing_extensions import override

from .event_dispatcher_interface import EventDispatcherInterface
from .exception import BadMethodCallError

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

    from ._introspectable_dispatcher import IntrospectableDispatcher
    from .event_subscriber_interface import EventSubscriberInterface

__all__ = ["ImmutableEventDispatcher"]

_EventT = TypeVar("_EventT")


@final
class ImmutableEventDispatcher(EventDispatcherInterface):
    """Dispatches through another dispatcher, and refuses every change to its listeners.

    A dispatcher shared for a process's lifetime is a poor place for a
    listener added at runtime: it would outlive the request, message or task
    that added it. Handing the dispatcher out wrapped in this keeps its
    listeners to those its builder registered. A listener that must live for
    one scope goes on a
    :class:`~xtr_event_dispatcher.scoped_event_dispatcher.ScopedEventDispatcher`
    wrapping this one.

    ```python
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(AuditSubscriber())
    shared = ImmutableEventDispatcher(dispatcher)

    shared.add_listener(OrderPlaced, send_receipt)  # BadMethodCallError
    ```
    """

    __slots__ = ("_dispatcher",)

    def __init__(self, dispatcher: IntrospectableDispatcher) -> None:
        """Wrap ``dispatcher``, which keeps dispatching and answering for its listeners."""
        self._dispatcher = dispatcher

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Dispatch through the wrapped dispatcher."""
        return await self._dispatcher.dispatch(event, event_name)

    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    @override
    def get_listeners(
        self,
        event_name: str | type | None = None,
    ) -> dict[str, list[Listener]] | list[Listener]:
        """Return the wrapped dispatcher's listeners."""
        if event_name is None:
            return self._dispatcher.get_listeners()

        return self._dispatcher.get_listeners(event_name)

    @override
    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        """Return the priority the wrapped dispatcher runs ``listener`` at."""
        return self._dispatcher.get_listener_priority(event_name, listener)

    @override
    def has_listeners(self, event_name: str | type | None = None) -> bool:
        """Tell whether the wrapped dispatcher has a listener for the event."""
        return self._dispatcher.has_listeners(event_name)

    @override
    def add_listener(
        self, event_name: str | type, listener: Listener, priority: int = 0
    ) -> NoReturn:
        """Refuse: the listeners cannot change.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("add_listener")

    @override
    def add_subscriber(self, subscriber: EventSubscriberInterface) -> NoReturn:
        """Refuse: the listeners cannot change.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("add_subscriber")

    @override
    def remove_listener(self, event_name: str | type, listener: Listener) -> NoReturn:
        """Refuse: the listeners cannot change.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("remove_listener")

    @override
    def remove_subscriber(self, subscriber: EventSubscriberInterface) -> NoReturn:
        """Refuse: the listeners cannot change.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("remove_subscriber")
