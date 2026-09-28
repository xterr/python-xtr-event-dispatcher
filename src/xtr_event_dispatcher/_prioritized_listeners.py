"""An event's listeners read with the priority each runs at, from any dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

    from ._introspectable_dispatcher import IntrospectableDispatcher

__all__ = ["prioritized_listeners"]


@runtime_checkable
class _KeepsPriorities(Protocol):
    def get_prioritized_listeners(self, event_name: str | type, /) -> list[tuple[int, Listener]]:
        """Return the event's listeners in running order, each with its priority."""
        ...


def prioritized_listeners(
    dispatcher: IntrospectableDispatcher, event_name: str
) -> list[tuple[int, Listener]]:
    """Return the event's listeners in running order, each with the priority it runs at.

    Read as pairs from a dispatcher that keeps them, so a listener registered
    at two priorities keeps both. Any other dispatcher is asked each
    listener's priority, which names one priority for a listener, however
    often it is registered.
    """
    if isinstance(dispatcher, _KeepsPriorities):
        return dispatcher.get_prioritized_listeners(event_name)
    return [
        (dispatcher.get_listener_priority(event_name, listener) or 0, listener)
        for listener in dispatcher.get_listeners(event_name)
    ]
