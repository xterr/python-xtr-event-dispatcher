"""The factories a dispatcher the container builds is registered with, traced or not."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated

from xtr_dependency_injection import AutowireDecorated, Target
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface

from xtr_event_dispatcher.compiled_event_dispatcher import CompiledEventDispatcher
from xtr_event_dispatcher.debug.traceable_event_dispatcher import TraceableEventDispatcher
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface

from .listener_map import ListenerMap

__all__ = ["EVENT_CHANNEL", "event_dispatcher_factory", "traceable_event_dispatcher_factory"]

EVENT_CHANNEL = "event"
"""The logging channel a traced dispatcher writes to."""

_NOT_IN_A_NAME = re.compile(r"\W")
"""What a dispatcher's name may hold that a function's may not, as in ``a.b``."""


def event_dispatcher_factory(name: str | None = None) -> Callable[..., EventDispatcherInterface]:
    """Return the factory of the dispatcher named ``name``; the default one for ``None``.

    A bundle owning a dispatcher of its own registers it under its name and
    tags it, and :class:`~xtr_event_dispatcher.bundle.RegisterListenersPass`
    hands it the listeners declared for it — ``@as_event_listener(dispatcher=name)``
    and the tags naming it::

        services.set(event_dispatcher_factory("audit"), qualifier="audit").add_tag(DISPATCHER_TAG)

    The factory builds a :class:`CompiledEventDispatcher`, each listener
    service fetched when an event first reaches it. One function per
    dispatcher, so each carries its own name in the container's report.
    """

    def event_dispatcher(
        listeners: ListenerMap, container: ContainerInterface
    ) -> EventDispatcherInterface:
        return CompiledEventDispatcher(
            {
                event: [
                    (reference.listener(container), priority) for priority, reference in references
                ]
                for event, references in listeners.by_event.items()
            },
        )

    if name is not None:
        event_dispatcher.__name__ = "event_dispatcher_" + _NOT_IN_A_NAME.sub("_", name)
        event_dispatcher.__qualname__ = event_dispatcher.__name__

    return event_dispatcher


def traceable_event_dispatcher_factory(*, logged: bool) -> Callable[..., TraceableEventDispatcher]:
    """Return the factory of a :class:`TraceableEventDispatcher` decorating a dispatcher.

    Register it decorating the dispatcher's key, tagged ``kernel.reset`` so
    each unit of work starts its trace afresh. ``logged`` writes the trace to
    the ``"event"`` channel; ask for it only when the logging bundle is
    active.
    """
    return _logged_traceable if logged else _traceable


def _traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
) -> TraceableEventDispatcher:
    """Trace ``dispatcher`` without logging."""
    return TraceableEventDispatcher(dispatcher)


def _logged_traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
    logger: Annotated[LoggerInterface, Target(EVENT_CHANNEL)],
) -> TraceableEventDispatcher:
    """Trace ``dispatcher``, writing to the ``"event"`` channel."""
    return TraceableEventDispatcher(dispatcher, logger)
