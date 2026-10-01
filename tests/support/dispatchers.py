"""A dispatcher written against the contracts alone, which cannot register listeners."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final, overload

from xtr_event_dispatcher_contracts import event_name_of

from xtr_event_dispatcher._listener_call import call_listener, positional_arity

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

__all__ = ["ReadOnlyDispatcher"]

_EventT = TypeVar("_EventT")


@final
class ReadOnlyDispatcher:
    """Dispatches the listeners it was built with, each at priority ``0``, and reads them."""

    def __init__(self, listeners: dict[str, list[Listener]]) -> None:
        self._listeners = listeners

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        name = event_name_of(type(event) if event_name is None else event_name)
        for listener in self._listeners.get(name, []):
            await call_listener(listener, positional_arity(listener), (event, name, self))
        return event

    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    def get_listeners(
        self, event_name: str | type | None = None
    ) -> dict[str, list[Listener]] | list[Listener]:
        if event_name is None:
            return {name: list(listeners) for name, listeners in self._listeners.items()}
        return list(self._listeners.get(event_name_of(event_name), []))

    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        listeners = self._listeners.get(event_name_of(event_name), [])
        return 0 if any(registered is listener for registered in listeners) else None

    def has_listeners(self, event_name: str | type | None = None) -> bool:
        if event_name is None:
            return any(self._listeners.values())
        return bool(self._listeners.get(event_name_of(event_name)))
