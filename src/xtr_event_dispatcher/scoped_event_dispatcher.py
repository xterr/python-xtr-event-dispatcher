"""Listeners added next to those of another dispatcher, without changing it."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, TypeVar, final, overload

from typing_extensions import override
from xtr_event_dispatcher_contracts import event_name_of

from .event_dispatcher import EventDispatcher

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

    from ._introspectable_dispatcher import IntrospectableDispatcher

__all__ = ["ScopedEventDispatcher"]

_EventT = TypeVar("_EventT")


@final
class ScopedEventDispatcher(EventDispatcher):
    """Adds listeners to those of another dispatcher, which is left as it is.

    Gives a listener the lifetime of a scope — a request, a console command, a
    test — when the dispatcher it has to run on is shared, and possibly one
    that cannot be changed at all.

    ```python
    scoped = ScopedEventDispatcher(shared)
    scoped.add_listener(OrderPlaced, collect)
    await scoped.dispatch(OrderPlaced(42))  # the shared listeners run too
    ```

    The first listener added here for an event copies that event's
    listeners from the wrapped dispatcher, at their priorities, so the two
    sets interleave by priority. An event nothing was added for here is
    dispatched by the wrapped dispatcher itself.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_dispatcher", "_merged")

    def __init__(self, dispatcher: IntrospectableDispatcher) -> None:
        """Wrap ``dispatcher``, whose listeners keep running for every event."""
        super().__init__()
        self._dispatcher = dispatcher
        self._merged: set[str] = set()

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Dispatch here when a listener was added for the event, else through the wrapped one."""
        name = event_name_of(type(event) if event_name is None else event_name)
        if super().has_listeners(name):
            return await super().dispatch(event, name)

        return await self._dispatcher.dispatch(event, name)

    @override
    def add_listener(self, event_name: str | type, listener: Listener, priority: int = 0) -> None:
        """Run ``listener`` for the event here, alongside the wrapped dispatcher's listeners."""
        name = event_name_of(event_name)
        self._merge(name)
        super().add_listener(name, listener, priority)

    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    @override
    def get_listeners(
        self,
        event_name: str | type | None = None,
    ) -> dict[str, list[Listener]] | list[Listener]:
        """Return the listeners the event runs, here or in the wrapped dispatcher."""
        if event_name is None:
            names = dict.fromkeys([*super().get_listeners(), *self._dispatcher.get_listeners()])
            return {name: self.get_listeners(name) for name in names}

        name = event_name_of(event_name)
        if super().has_listeners(name):
            return super().get_listeners(name)

        return self._dispatcher.get_listeners(name)

    @override
    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        """Return the priority ``listener`` runs at, here or in the wrapped dispatcher."""
        name = event_name_of(event_name)
        if super().has_listeners(name):
            return super().get_listener_priority(name, listener)

        return self._dispatcher.get_listener_priority(name, listener)

    @override
    def has_listeners(self, event_name: str | type | None = None) -> bool:
        """Tell whether the event has a listener here or in the wrapped dispatcher."""
        return super().has_listeners(event_name) or self._dispatcher.has_listeners(event_name)

    def _merge(self, name: str) -> None:
        """Copy the wrapped dispatcher's listeners of ``name`` here, once."""
        if name in self._merged:
            return

        self._merged.add(name)
        for listener in self._dispatcher.get_listeners(name):
            priority = self._dispatcher.get_listener_priority(name, listener)
            super().add_listener(name, listener, priority or 0)
