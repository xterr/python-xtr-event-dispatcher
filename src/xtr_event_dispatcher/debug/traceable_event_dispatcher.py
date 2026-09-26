"""A dispatcher that records which listeners ran, which did not, and which events nobody heard."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar, TypeVar, final, overload

from typing_extensions import override
from xtr_event_dispatcher_contracts import StoppableEventInterface, event_name_of

from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface

from .wrapped_listener import WrappedListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener
    from xtr_logging_contracts import LoggerInterface

    from xtr_event_dispatcher.event_subscriber_interface import EventSubscriberInterface

    from .listener_info import ListenerInfo

__all__ = ["TraceableEventDispatcher"]

_EventT = TypeVar("_EventT")


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
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_called", "_dispatcher", "_logger", "_orphaned")

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Trace ``dispatcher``, writing to ``logger`` when one is given."""
        self._dispatcher = dispatcher
        self._logger = logger
        self._orphaned: list[str] = []
        # Event name -> [listener as registered, what it was described as, calls].
        self._called: dict[str, list[tuple[Listener, ListenerInfo, int]]] = {}

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

        listeners = self._wrap(name)
        try:
            for listener in listeners:
                if stoppable is not None and stoppable.is_propagation_stopped():
                    break
                await listener(event, name, self)
        finally:
            self._record(name, listeners)

        return event

    def get_called_listeners(self) -> list[ListenerInfo]:
        """Describe every listener that ran since the last reset, with how often it ran."""
        return [
            replace(info, calls=calls)
            for called in self._called.values()
            for _, info, calls in called
        ]

    def get_not_called_listeners(self) -> list[ListenerInfo]:
        """Describe every registered listener that has not run for its event since the last reset.

        Ordered by event name, then from the highest priority down.
        """
        not_called: list[ListenerInfo] = []
        for name, listeners in self._dispatcher.get_listeners().items():
            called = [listener for listener, _, _ in self._called.get(name, ())]
            not_called.extend(
                WrappedListener(listener, self._dispatcher).get_info(name)
                for listener in listeners
                if listener not in called
            )

        return sorted(not_called, key=lambda info: (info.event, -(info.priority or 0)))

    def get_orphaned_events(self) -> list[str]:
        """Return the events dispatched with nobody listening since the last reset, in order."""
        return list(self._orphaned)

    def reset(self) -> None:
        """Forget everything recorded, so the next unit of work starts from nothing."""
        self._orphaned = []
        self._called = {}

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

    def _wrap(self, name: str) -> list[WrappedListener]:
        if not self._dispatcher.has_listeners(name):
            self._orphaned.append(name)
            return []

        return [
            WrappedListener(listener, self._dispatcher)
            for listener in self._dispatcher.get_listeners(name)
        ]

    def _record(self, name: str, listeners: list[WrappedListener]) -> None:
        skipped = False
        for listener in listeners:
            context: dict[str, object] = {"event": name, "listener": listener.get_pretty()}
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
        called = self._called.setdefault(name, [])
        original = listener.get_wrapped_listener()
        for index, (seen, info, calls) in enumerate(called):
            if seen == original:
                called[index] = (seen, info, calls + 1)
                return

        called.append((original, listener.get_info(name), 1))

    def _log(self, message: str, context: dict[str, object]) -> None:
        if self._logger is not None:
            self._logger.debug(message, context)
