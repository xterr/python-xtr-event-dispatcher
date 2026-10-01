"""A dispatcher another one can wrap: one that dispatches, and tells which listeners it has."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xtr_event_dispatcher_contracts import EventDispatcherInterface, ListenerIntrospectionInterface

__all__ = ["IntrospectableDispatcherInterface"]


@runtime_checkable
class IntrospectableDispatcherInterface(
    EventDispatcherInterface, ListenerIntrospectionInterface, Protocol
):
    """A dispatcher that also tells which listeners it has.

    What :class:`~xtr_event_dispatcher.immutable_event_dispatcher.ImmutableEventDispatcher`
    and :class:`~xtr_event_dispatcher.scoped_event_dispatcher.ScopedEventDispatcher`
    wrap: both contracts at once, and nothing that changes the listeners — so
    a wrapper accepts a dispatcher that cannot be changed as readily as one
    that can, and one written against the contracts alone.
    """
