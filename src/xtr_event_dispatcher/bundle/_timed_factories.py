"""The traced dispatcher's factories that also time every listener on the stopwatch.

Imported only once xtr-stopwatch is known to be installed: the container reads
the ``Stopwatch`` annotation at runtime, so this module cannot load without it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from xtr_dependency_injection import AutowireDecorated, Target
from xtr_dependency_injection.integration import register_detached_variable
from xtr_logging_contracts import LoggerInterface
from xtr_stopwatch import Stopwatch

from xtr_event_dispatcher.debug.traceable_event_dispatcher import TraceableEventDispatcher
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface

from .event_dispatcher_factory import EVENT_CHANNEL

__all__ = ["stopwatch", "timed_traceable_event_dispatcher_factory"]


def stopwatch() -> Stopwatch:
    """Build the stopwatch on its own monotonic clock.

    A factory rather than the class, so the container never hands it the
    application's clock: a wall clock would let a correction bend a duration.
    Every new connection starts with nothing timed.
    """
    timer = Stopwatch()
    register_detached_variable(*timer.detached_variable)
    return timer


def timed_traceable_event_dispatcher_factory(
    *, logged: bool
) -> Callable[..., TraceableEventDispatcher]:
    """Return the factory of a traced dispatcher timing its listeners on the ``Stopwatch``."""
    return _logged_timed_traceable if logged else _timed_traceable


def _timed_traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
    stopwatch: Stopwatch,
) -> TraceableEventDispatcher:
    """Trace ``dispatcher`` without logging, timing each listener on ``stopwatch``."""
    return _detached(TraceableEventDispatcher(dispatcher, stopwatch=stopwatch))


def _logged_timed_traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
    logger: Annotated[LoggerInterface, Target(EVENT_CHANNEL)],
    stopwatch: Stopwatch,
) -> TraceableEventDispatcher:
    """Trace ``dispatcher``, writing to the ``"event"`` channel and timing on ``stopwatch``."""
    return _detached(TraceableEventDispatcher(dispatcher, logger, stopwatch))


def _detached(traced: TraceableEventDispatcher) -> TraceableEventDispatcher:
    """Have every new connection start outside ``traced``'s unit of work."""
    register_detached_variable(*traced.detached_variable)
    return traced
