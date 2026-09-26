"""What a dispatcher wrapping another needs of it: dispatching, and reading its listeners."""

from __future__ import annotations

from typing import Protocol

from xtr_event_dispatcher_contracts import EventDispatcherInterface, ListenerIntrospectionInterface

__all__ = ["IntrospectableDispatcher"]


class IntrospectableDispatcher(EventDispatcherInterface, ListenerIntrospectionInterface, Protocol):
    """A dispatcher that also tells which listeners it has.

    Both contracts at once, and nothing that changes the listeners — so a
    wrapper accepts a dispatcher that cannot be changed as readily as one
    that can.
    """
