"""A dispatcher that records which listeners ran, which did not, and which events nobody heard."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
from typing import TYPE_CHECKING, TypeVar, final, overload

from typing_extensions import override
from xtr_event_dispatcher_contracts import StoppableEventInterface, event_name_of

from xtr_event_dispatcher._prioritized_listeners import prioritized_listeners
from xtr_event_dispatcher.event_dispatcher import EventDispatcher
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface

from .wrapped_listener import WrappedListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener, ListenerIntrospectionInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_event_dispatcher.event_subscriber_interface import EventSubscriberInterface

    from .listener_info import ListenerInfo

__all__ = ["TraceableEventDispatcher"]

_EventT = TypeVar("_EventT")


@final
class _Trace:
    """What one unit of work recorded: the listeners that ran, the events nobody heard.

    Mutated in place, so a synchronous endpoint run in a copied context
    records into the same trace the context still points at.
    """

    __slots__ = ("called", "orphaned", "outer")

    def __init__(self, outer: _Trace | None = None) -> None:
        self.outer = outer
        # Insertion-ordered and without repeats: a hot unheard event is listed once.
        self.orphaned: dict[str, None] = {}
        # Event name -> [listener as registered, its calls and time so far].
        self.called: dict[str, list[tuple[Listener, ListenerInfo]]] = {}


@final
class TraceableEventDispatcher(EventDispatcherInterface):
    """Dispatches through another dispatcher's listeners, keeping track of what happened.

    For development: it answers which listeners ran and how often, which
    never ran, and which events were dispatched with nobody listening — and,
    given a logger, writes each of those as a debug record. Everything else is
    the wrapped dispatcher's: registering listeners, reading them.

    ```python
    traced = TraceableEventDispatcher(dispatcher, logger)
    await traced.dispatch(OrderPlaced(42))
    traced.get_called_listeners()  # [ListenerInfo(event=..., pretty=..., calls=1), ...]
    ```

    It runs the listeners itself, so a listener receives this dispatcher. What
    it records grows until :meth:`reset`, which a long-running process calls
    between units of work.

    Each listener's runs are timed, so :meth:`get_called_listeners` tells where
    a slow dispatch spent its time. Wrapping an
    :class:`~xtr_event_dispatcher.event_dispatcher.EventDispatcher`, it leaves
    running the listeners to it and only watches each call; any other
    dispatcher's listeners it runs itself, asking before each whether it is
    still registered.

    :meth:`begin_unit` and :meth:`end_unit` open a trace scoped to the calling
    context, so overlapping units of work — concurrent requests — each record
    only their own. A unit of work exists only when tracing is on: the bundle
    wraps a dispatcher in this one only in debug mode.
    """

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Trace ``dispatcher``, writing to ``logger`` when one is given."""
        self._dispatcher = dispatcher
        self._logger = logger
        self._trace = _Trace()
        self._unit: ContextVar[_Trace | None] = ContextVar("event_trace_unit", default=None)

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Run the wrapped dispatcher's listeners of the event, recording each outcome."""
        name = event_name_of(type(event) if event_name is None else event_name)
        stoppable = event if isinstance(event, StoppableEventInterface) else None
        if (
            self._logger is not None
            and stoppable is not None
            and stoppable.is_propagation_stopped()
        ):
            self._logger.debug(
                'The "{event}" event is already stopped. No listeners have been called.',
                {"event": name},
            )

        if not self._dispatcher.has_listeners(name):
            self._active().orphaned[name] = None
            return event

        if isinstance(self._dispatcher, EventDispatcher):
            watch = _Watch(name, self._dispatcher)
            try:
                _ = await self._dispatcher.dispatch_through(
                    event, name, dispatcher=self, call=watch
                )
            finally:
                self._record(name, watch.listeners)
            return event

        listeners = [
            WrappedListener(listener, self._dispatcher)
            for listener in self._dispatcher.get_listeners(name)
        ]
        try:
            for listener in listeners:
                if stoppable is not None and stoppable.is_propagation_stopped():
                    break
                # Removed since the dispatch began: skipped, as an untraced dispatch would.
                if (
                    self._dispatcher.get_listener_priority(name, listener.get_wrapped_listener())
                    is None
                ):
                    continue
                await listener(event, name, self)
        finally:
            self._record(name, listeners)

        return event

    def begin_unit(self) -> None:
        """Open a trace scoped to the calling context, for one unit of work of its own."""
        _ = self._unit.set(_Trace(self._unit.get()))

    def end_unit(self) -> None:
        """Close the unit opened in this context; recording returns to where it was before."""
        unit = self._unit.get()
        _ = self._unit.set(None if unit is None else unit.outer)

    def get_called_listeners(self) -> list[ListenerInfo]:
        """Describe every listener that ran since the last reset, how often and for how long."""
        return [info for called in self._active().called.values() for _, info in called]

    def get_not_called_listeners(self) -> list[ListenerInfo]:
        """Describe every registered listener that has not run for its event since the last reset.

        Ordered by event name, then from the highest priority down.
        """
        called_by_name = self._active().called
        not_called: list[ListenerInfo] = []
        for name, listeners in self._dispatcher.get_listeners().items():
            called = [listener for listener, _ in called_by_name.get(name, ())]
            not_called.extend(
                WrappedListener(listener, self._dispatcher).get_info(name)
                for listener in listeners
                if listener not in called
            )

        return sorted(not_called, key=lambda info: (info.event, -(info.priority or 0)))

    def get_orphaned_events(self) -> list[str]:
        """Return the events dispatched with nobody listening since the last reset.

        Each is listed once, in the order it was first dispatched.
        """
        return list(self._active().orphaned)

    def reset(self) -> None:
        """Forget everything the active trace recorded, so the next unit starts from nothing."""
        trace = self._active()
        trace.orphaned.clear()
        trace.called.clear()

    def _active(self) -> _Trace:
        """Return the trace recording is going to: the open unit's, or the instance's."""
        unit = self._unit.get()
        return self._trace if unit is None else unit

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

    def get_prioritized_listeners(self, event_name: str | type, /) -> list[tuple[int, Listener]]:
        """Return the wrapped dispatcher's listeners of the event, each with its priority."""
        return prioritized_listeners(self._dispatcher, event_name_of(event_name))

    @override
    def has_listeners(self, event_name: str | type | None = None) -> bool:
        """Tell whether the wrapped dispatcher has a listener for the event."""
        return self._dispatcher.has_listeners(event_name)

    @override
    def add_listener(self, event_name: str | type, listener: Listener, priority: int = 0) -> None:
        """Add ``listener`` to the wrapped dispatcher."""
        self._dispatcher.add_listener(event_name, listener, priority)

    @override
    def add_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Add ``subscriber`` to the wrapped dispatcher."""
        self._dispatcher.add_subscriber(subscriber)

    @override
    def remove_listener(self, event_name: str | type, listener: Listener) -> None:
        """Remove ``listener`` from the wrapped dispatcher."""
        self._dispatcher.remove_listener(event_name, listener)

    @override
    def remove_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Remove ``subscriber`` from the wrapped dispatcher."""
        self._dispatcher.remove_subscriber(subscriber)

    def _record(self, name: str, listeners: list[WrappedListener]) -> None:
        skipped = False
        for listener in listeners:
            context: dict[str, object] = {
                "event": name,
                "listener": listener.get_pretty(),
                "duration": listener.get_duration(),
            }
            if listener.was_called():
                self._log('Notified event "{event}" to listener "{listener}".', context)
                self._count(name, listener)
            if skipped:
                self._log('Listener "{listener}" was not called for event "{event}".', context)
            if listener.stopped_propagation():
                self._log(
                    'Listener "{listener}" stopped propagation of the event "{event}".', context
                )
                skipped = True

    def _count(self, name: str, listener: WrappedListener) -> None:
        called = self._active().called.setdefault(name, [])
        original = listener.get_wrapped_listener()
        for index, (seen, info) in enumerate(called):
            if seen == original:
                called[index] = (
                    seen,
                    replace(
                        info, calls=info.calls + 1, duration=info.duration + listener.get_duration()
                    ),
                )
                return

        called.append((original, listener.get_info(name, calls=1)))

    def _log(self, message: str, context: dict[str, object]) -> None:
        if self._logger is not None:
            self._logger.debug(message, context)


@final
class _Watch:
    """Watches the calls an :class:`EventDispatcher` makes for one dispatch.

    It holds a wrapper per listener, in the order the dispatcher runs them; a
    call is matched to the next wrapper of the listener it names, so a
    listener registered twice is told apart by position.
    """

    __slots__ = ("_dispatcher", "_name", "_next", "listeners")

    def __init__(self, name: str, dispatcher: ListenerIntrospectionInterface) -> None:
        self._name = name
        self._dispatcher = dispatcher
        self._next = 0
        self.listeners = [
            WrappedListener(listener, priority=priority)
            for priority, listener in prioritized_listeners(dispatcher, name)
        ]

    async def __call__(
        self,
        registered: Listener,
        listener: Listener,
        arity: int,
        arguments: tuple[object, ...],
    ) -> None:
        index = self._position(registered)
        wrapped = self.listeners[index]
        if listener is not registered:
            # A lazy listener built just now: what it built is what ran.
            priority = wrapped.get_info(self._name).priority
            wrapped = self.listeners[index] = WrappedListener(listener, priority=priority)
        await wrapped.run(arity, arguments)

    def _position(self, registered: Listener) -> int:
        for index in range(self._next, len(self.listeners)):
            if self.listeners[index].get_wrapped_listener() is registered:
                self._next = index + 1
                return index

        # Not among those the dispatch started with: watched all the same.
        self.listeners.append(WrappedListener(registered, self._dispatcher))
        self._next = len(self.listeners)
        return self._next - 1
