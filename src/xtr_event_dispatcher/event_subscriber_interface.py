"""A class that declares, in one place, every event it listens to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeAlias, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .subscribed_listener import SubscribedListener

__all__ = ["EventSubscriberInterface", "SubscribedEvents"]

SubscribedEvents: TypeAlias = (
    "str | tuple[str, int] | SubscribedListener | list[str | tuple[str, int] | SubscribedListener]"
)
"""What a subscriber declares for one event.

One listener is a method name, a ``(method, priority)`` pair, or a
:class:`~xtr_event_dispatcher.subscribed_listener.SubscribedListener`; a list
of those declares several listeners for the same event.
"""


@runtime_checkable
class EventSubscriberInterface(Protocol):
    """Knows which events it listens to, and which of its methods handles each.

    Adding a subscriber to a dispatcher registers one listener per declared
    method. A listener without a priority runs at ``0``.

    ```python
    class OrderMailer(EventSubscriberInterface):
        @classmethod
        @override
        def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
            return {
                OrderPlaced: "on_placed",
                OrderShipped: ("on_shipped", 10),
                OrderCancelled: ["notify_customer", {"method": "notify_warehouse", "priority": -5}],
            }
    ```

    A container derives the subscriber's listeners from the class, before any
    instance exists, so the declaration must not depend on state: put what
    varies at runtime in the methods it names.
    """

    @classmethod
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Map each event — its name, or its class — to the listeners declared for it."""
        ...
