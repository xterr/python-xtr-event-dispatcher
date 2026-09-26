"""A dispatcher whose listeners are fixed when it is built."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NoReturn, final

from typing_extensions import override

from .event_dispatcher import EventDispatcher
from .exception import BadMethodCallError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_event_dispatcher_contracts import Listener

    from .event_subscriber_interface import EventSubscriberInterface

__all__ = ["CompiledEventDispatcher"]


@final
class CompiledEventDispatcher(EventDispatcher):
    """Dispatches to listeners described once, up front, and refuses any change after.

    What a container builds: it knows every listener while it compiles, so it
    hands them over in one go, usually as
    :class:`~xtr_event_dispatcher.lazy_listener.LazyListener` objects so that
    nothing is built before an event needs it.

    ```python
    dispatcher = CompiledEventDispatcher(
        {
            OrderPlaced: [(LazyListener(mailer_factory, "on_placed"), 10), (audit, 0)],
        }
    )
    ```

    Unlike an
    :class:`~xtr_event_dispatcher.immutable_event_dispatcher.ImmutableEventDispatcher`
    wrapped around a dispatcher, it runs its listeners itself, so the
    dispatcher a listener receives is this one — and cannot be changed
    either. A listener that must live for one scope goes on a
    :class:`~xtr_event_dispatcher.scoped_event_dispatcher.ScopedEventDispatcher`
    wrapping it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ()

    def __init__(self, listeners: Mapping[str | type, Sequence[tuple[Listener, int]]]) -> None:
        """Register every listener, event by event, each at its priority.

        Listeners sharing a priority run in the order given.

        Raises:
            ListenerSignatureError: When a listener cannot be called the way a
                dispatcher calls listeners.
        """
        super().__init__()
        for event_name, entries in listeners.items():
            for listener, priority in entries:
                super().add_listener(event_name, listener, priority)

    @override
    def add_listener(
        self, event_name: str | type, listener: Listener, priority: int = 0
    ) -> NoReturn:
        """Refuse: the listeners were fixed when the dispatcher was built.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("add_listener")

    @override
    def add_subscriber(self, subscriber: EventSubscriberInterface) -> NoReturn:
        """Refuse: the listeners were fixed when the dispatcher was built.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("add_subscriber")

    @override
    def remove_listener(self, event_name: str | type, listener: Listener) -> NoReturn:
        """Refuse: the listeners were fixed when the dispatcher was built.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("remove_listener")

    @override
    def remove_subscriber(self, subscriber: EventSubscriberInterface) -> NoReturn:
        """Refuse: the listeners were fixed when the dispatcher was built.

        Raises:
            BadMethodCallError: Always.
        """
        raise BadMethodCallError("remove_subscriber")
