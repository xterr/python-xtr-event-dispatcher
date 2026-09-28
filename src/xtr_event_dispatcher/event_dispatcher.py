"""Listeners registered by event name, run from the highest priority down."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, TypeVar, overload

from typing_extensions import override
from xtr_event_dispatcher_contracts import StoppableEventInterface, event_name_of

from ._listener_call import call_listener, positional_arity
from ._subscribed_events import bind, listeners_subscribed_by
from .event_dispatcher_interface import EventDispatcherInterface
from .exception import InvalidSubscriberError
from .lazy_listener import LazyListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

    from .event_subscriber_interface import EventSubscriberInterface

__all__ = ["EventDispatcher"]

_EventT = TypeVar("_EventT")


@dataclass(frozen=True, slots=True)
class _Entry:
    """A registered listener, with how many arguments it takes worked out once."""

    listener: Listener
    arity: int


@dataclass(frozen=True, slots=True)
class _PendingRemoval:
    """``obj.method`` removed while ``unbuilt`` lazy listeners may still build into it."""

    obj: object
    method: str
    unbuilt: tuple[_Entry, ...]


class EventDispatcher(EventDispatcherInterface):
    """Runs the listeners of each event, highest priority first.

    ```python
    dispatcher = EventDispatcher()
    dispatcher.add_listener(OrderPlaced, send_receipt, priority=10)
    dispatcher.add_subscriber(AuditSubscriber())

    await dispatcher.dispatch(OrderPlaced(42))
    ```

    Listeners sharing a priority run in the order they were added. One added
    while an event is dispatched first runs on the next dispatch; one removed
    meanwhile does not run for the rest of it. A
    :class:`~xtr_event_dispatcher.lazy_listener.LazyListener` is built just
    before it first runs, so one that a stopped event never reaches is never
    built — and until then it is the lazy listener, not a bound method, that
    :meth:`get_listeners` returns.

    Removing ``obj.method`` while a lazy listener of the event is still
    unbuilt cannot tell whether that listener is the one: the removal is kept,
    and applied when it is built — to the lazy listeners registered at the
    time of the removal only, never to one added after it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_listeners", "_pending_removals", "_sorted")

    def __init__(self) -> None:
        """Start with no listener."""
        # Event name -> priority -> entries in registration order. An event or
        # a priority left without entries is dropped, so presence means
        # "has listeners".
        self._listeners: dict[str, dict[int, list[_Entry]]] = {}
        self._sorted: dict[str, list[_Entry]] = {}
        # Event name -> (object, method) removed while lazy listeners of the
        # event were unbuilt, with those listeners; any of them that builds
        # into it is dropped.
        self._pending_removals: dict[str, list[_PendingRemoval]] = {}

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Run every listener of the event, highest priority first, and return it.

        See the contract's
        :meth:`~xtr_event_dispatcher_contracts.event_dispatcher_interface.EventDispatcherInterface.dispatch`.
        """
        name = event_name_of(type(event) if event_name is None else event_name)
        stoppable = event if isinstance(event, StoppableEventInterface) else None
        arguments = (event, name, self)

        # A snapshot: a listener added while this dispatch runs waits for the next one.
        # One removed meanwhile is skipped, so a listener can unsubscribe another at once.
        running = self._sort(name)
        current = running
        registered: set[int] | None = None
        for entry in running:
            if stoppable is not None and stoppable.is_propagation_stopped():
                break
            if self._sorted.get(name) is not current:
                current = self._sort(name)
                registered = {id(candidate) for candidate in current}
            if registered is not None and id(entry) not in registered:
                continue

            listener = entry.listener
            current = (
                await self._build(name, entry, listener)
                if isinstance(listener, LazyListener)
                else entry
            )
            if current is not None:
                await call_listener(current.listener, current.arity, arguments)

        return event

    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    @override
    def get_listeners(
        self,
        event_name: str | type | None = None,
    ) -> dict[str, list[Listener]] | list[Listener]:
        """Return the listeners of one event in the order they run, or of every event."""
        if event_name is not None:
            return [entry.listener for entry in self._sort(event_name_of(event_name))]

        return {name: [entry.listener for entry in self._sort(name)] for name in self._listeners}

    @override
    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        """Return the priority ``listener`` runs at for the event, ``None`` when it does not."""
        for priority, entries in self._listeners.get(event_name_of(event_name), {}).items():
            if any(_same(entry.listener, listener) for entry in entries):
                return priority

        return None

    @override
    def has_listeners(self, event_name: str | type | None = None) -> bool:
        """Tell whether the event — or, given ``None``, any event — has a listener."""
        if event_name is None:
            return bool(self._listeners)

        return event_name_of(event_name) in self._listeners

    @override
    def add_listener(self, event_name: str | type, listener: Listener, priority: int = 0) -> None:
        """Run ``listener`` whenever the event is dispatched, at ``priority``.

        A lazy listener that has already been built is registered as what it
        built into.

        Raises:
            ListenerSignatureError: When ``listener`` cannot be called the way
                a dispatcher calls listeners.
        """
        if isinstance(listener, LazyListener) and listener.resolved is not None:
            listener = listener.resolved

        name = event_name_of(event_name)
        entry = _Entry(listener, positional_arity(listener))
        self._listeners.setdefault(name, {}).setdefault(priority, []).append(entry)
        _ = self._sorted.pop(name, None)

    @override
    def remove_listener(self, event_name: str | type, listener: Listener) -> None:
        """Stop running ``listener`` for the event; one that was not registered is ignored."""
        name = event_name_of(event_name)
        by_priority = self._listeners.get(name)
        if by_priority is None:
            return

        unbuilt: list[_Entry] = []
        for priority, entries in list(by_priority.items()):
            kept = [entry for entry in entries if not _same(entry.listener, listener)]
            unbuilt.extend(entry for entry in kept if _is_unbuilt(entry.listener))
            if kept:
                by_priority[priority] = kept
            else:
                del by_priority[priority]

        if not by_priority:
            del self._listeners[name]
        _ = self._sorted.pop(name, None)

        owner = _owner_of(listener)
        if unbuilt and owner is not None:
            removal = _PendingRemoval(owner[0], owner[1], tuple(unbuilt))
            self._pending_removals.setdefault(name, []).append(removal)
        self._prune_pending_removals(name)

    @override
    def add_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Add a listener for every method ``subscriber`` declares.

        Raises:
            InvalidSubscriberError: When a declaration cannot be registered —
                including ``before`` or ``after`` without a ``priority``, which
                only a container can honour.
        """
        for declared in listeners_subscribed_by(type(subscriber)):
            if declared.priority is None and (declared.before or declared.after):
                raise InvalidSubscriberError(
                    type(subscriber).__qualname__,
                    declared.event_name,
                    f'the "before"/"after" keys of {declared.method!r} need a "priority" when '
                    f"the subscriber is added with add_subscriber(): they only apply to "
                    f"subscribers a container registers",
                )
            self.add_listener(
                declared.event_name,
                bind(subscriber, declared),
                declared.priority or 0,
            )

    @override
    def remove_subscriber(self, subscriber: EventSubscriberInterface) -> None:
        """Remove every listener :meth:`add_subscriber` added for ``subscriber``."""
        for declared in listeners_subscribed_by(type(subscriber)):
            self.remove_listener(declared.event_name, bind(subscriber, declared))

    def get_prioritized_listeners(self, event_name: str | type, /) -> list[tuple[int, Listener]]:
        """Return the event's listeners in the order they run, each with its priority.

        A listener registered at two priorities appears at both, which
        :meth:`get_listener_priority` cannot say.
        """
        by_priority = self._listeners.get(event_name_of(event_name), {})
        return [
            (priority, entry.listener)
            for priority in sorted(by_priority, reverse=True)
            for entry in by_priority[priority]
        ]

    async def build_listener(
        self, event_name: str | type, listener: LazyListener
    ) -> Listener | None:
        """Build ``listener``, a lazy listener of the event, and put what it built in its place.

        What a dispatch reaching it does — for a dispatcher that runs this
        one's listeners itself, as the traceable one does, so the lazy
        listener is replaced there too.

        Returns:
            What to run: the built listener, or ``None`` when ``listener`` is
            no longer registered for the event or a pending removal drops it.
        """
        name = event_name_of(event_name)
        for entry in self._sort(name):
            if entry.listener is listener:
                built = await self._build(name, entry, listener)
                return None if built is None else built.listener
        return None

    def _sort(self, name: str) -> list[_Entry]:
        """Return the event's entries in running order, sorted once until they change."""
        cached = self._sorted.get(name)
        if cached is not None:
            return cached

        by_priority = self._listeners.get(name, {})
        entries = [
            entry
            for priority in sorted(by_priority, reverse=True)
            for entry in by_priority[priority]
        ]
        self._sorted[name] = entries

        return entries

    async def _build(self, name: str, entry: _Entry, lazy: LazyListener) -> _Entry | None:
        """Build ``entry``'s lazy listener and put what it built in the entry's place.

        Returns:
            The built entry, or ``None`` when a pending removal drops it.
        """
        # Building may add listeners to this very event: they land in the
        # lists below, after this entry, and are sorted in on the next dispatch.
        listener = await lazy.resolve()
        owner = _owner_of(listener)
        removed = owner is not None and any(
            removal.obj is owner[0]
            and removal.method == owner[1]
            and any(waiting is entry for waiting in removal.unbuilt)
            for removal in self._pending_removals.get(name, ())
        )
        built = None if removed else _Entry(listener, positional_arity(listener))
        self._replace(name, entry, built)

        return built

    def _replace(self, name: str, entry: _Entry, built: _Entry | None) -> None:
        by_priority = self._listeners.get(name, {})
        for priority, entries in list(by_priority.items()):
            for index, candidate in enumerate(entries):
                if candidate is not entry:
                    continue
                if built is None:
                    del entries[index]
                else:
                    entries[index] = built
                if not entries:
                    del by_priority[priority]
                break

        if not by_priority:
            _ = self._listeners.pop(name, None)
        _ = self._sorted.pop(name, None)
        self._prune_pending_removals(name)

    def _prune_pending_removals(self, name: str) -> None:
        """Forget, in each pending removal, the lazy listeners built or removed since."""
        removals = self._pending_removals.get(name)
        if not removals:
            return
        waiting = [
            entry
            for entries in self._listeners.get(name, {}).values()
            for entry in entries
            if _is_unbuilt(entry.listener)
        ]
        kept: list[_PendingRemoval] = []
        for removal in removals:
            unbuilt = tuple(
                entry for entry in removal.unbuilt if any(entry is other for other in waiting)
            )
            if unbuilt:
                kept.append(_PendingRemoval(removal.obj, removal.method, unbuilt))
        if kept:
            self._pending_removals[name] = kept
        else:
            _ = self._pending_removals.pop(name, None)


def _same(registered: Listener, listener: Listener) -> bool:
    """Tell whether ``listener`` designates the ``registered`` one.

    Bound methods of one object compare equal however often they are taken,
    and a built lazy listener is also known by what it built into.
    """
    if registered is listener or registered == listener:
        return True
    if isinstance(registered, LazyListener):
        return registered.resolved is not None and registered.resolved == listener
    if isinstance(listener, LazyListener):
        return listener.resolved is not None and listener.resolved == registered

    return False


def _is_unbuilt(listener: Listener) -> bool:
    return isinstance(listener, LazyListener) and listener.resolved is None


def _owner_of(listener: Listener) -> tuple[object, str] | None:
    """Return the object and method a listener calls, as a lazy listener would build it.

    A bound method is its object and method; a callable object is itself and
    ``"__call__"``. A function belongs to no object, so no lazy listener can
    build into it.
    """
    if inspect.ismethod(listener):
        return listener.__self__, listener.__name__
    if inspect.isroutine(listener) or isinstance(listener, type | LazyListener):
        return None

    return listener, "__call__"
