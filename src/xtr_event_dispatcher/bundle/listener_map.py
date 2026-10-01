"""A dispatcher's listeners as the container hands them over: each event's, in running order."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import event_name_of

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ._listener_reference import ListenerReference

__all__ = ["ListenerMap"]


@final
class ListenerMap:
    """Event name -> ``(priority, listener)`` pairs, in the order they run.

    What :class:`~xtr_event_dispatcher.bundle.RegisterListenersPass` sets as
    every tagged dispatcher's ``listeners`` argument, worked out while the
    container is built; each entry becomes a real listener only when the
    dispatcher is built, and a service one only when an event reaches it.

    A plain holder, not a mapping: the container resolves ``%name%``
    references in the mappings and dataclasses it is given as arguments, and
    an event name is not one.
    """

    __slots__ = ("by_event",)

    def __init__(self, by_event: Mapping[str, tuple[tuple[int, ListenerReference], ...]]) -> None:
        """Hold ``by_event``."""
        self.by_event = by_event

    def with_listeners_of(self, other: ListenerMap, events: Iterable[str | type]) -> ListenerMap:
        """Return a copy that also runs ``other``'s listeners of ``events``.

        Both sets interleave by priority; at equal priority this map's run
        first. How a dispatcher takes the listeners another one has for the
        events that bubble up to it — the security bundle gives every
        firewall's dispatcher the main dispatcher's listeners of the security
        events.
        """
        merged = dict(self.by_event)
        for event in dict.fromkeys(map(event_name_of, events)):
            added = other.by_event.get(event, ())
            if added:
                both = (*merged.get(event, ()), *added)
                merged[event] = tuple(sorted(both, key=lambda pair: -pair[0]))
        return ListenerMap(merged)
