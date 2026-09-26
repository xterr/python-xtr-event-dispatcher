"""A listener wrapped so that a traceable dispatcher knows what became of it."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from xtr_event_dispatcher_contracts import StoppableEventInterface

from xtr_event_dispatcher._listener_call import call_listener, positional_arity
from xtr_event_dispatcher._naming import listener_name
from xtr_event_dispatcher.lazy_listener import LazyListener

from .listener_info import ListenerInfo

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener, ListenerIntrospectionInterface

__all__ = ["WrappedListener"]


@final
class WrappedListener:
    """Runs a listener as a dispatcher would, remembering whether it ran and stopped the event.

    One is made per listener per dispatch, so what it remembers is about that
    dispatch alone.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_arity",
        "_called",
        "_dispatcher",
        "_listener",
        "_priority",
        "_stopped_propagation",
    )

    def __init__(
        self,
        listener: Listener,
        dispatcher: ListenerIntrospectionInterface | None = None,
        priority: int | None = None,
    ) -> None:
        """Wrap ``listener``.

        Args:
            listener: What to run.
            dispatcher: Where to ask the listener's priority, when not given.
            priority: The priority it runs at, when already known.
        """
        self._listener = listener
        self._dispatcher = dispatcher
        self._priority = priority
        self._arity = positional_arity(listener)
        self._called = False
        self._stopped_propagation = False

    def get_wrapped_listener(self) -> Listener:
        """Return the listener as it was registered."""
        return self._listener

    def was_called(self) -> bool:
        """Tell whether the listener ran."""
        return self._called

    def stopped_propagation(self) -> bool:
        """Tell whether the event was stopped once the listener had run."""
        return self._stopped_propagation

    def get_pretty(self) -> str:
        """Return a readable name for the listener."""
        return _pretty_name(self._listener)

    def get_info(self, event_name: str, calls: int = 0) -> ListenerInfo:
        """Describe the listener as a listener of ``event_name``."""
        if self._priority is None and self._dispatcher is not None:
            self._priority = self._dispatcher.get_listener_priority(event_name, self._listener)

        return ListenerInfo(event_name, self._priority, self.get_pretty(), calls)

    async def __call__(self, event: object, event_name: str, dispatcher: object) -> None:
        """Run the listener with what it takes of the three arguments, and note the outcome."""
        self._called = True
        await call_listener(self._listener, self._arity, (event, event_name, dispatcher))
        if isinstance(event, StoppableEventInterface) and event.is_propagation_stopped():
            self._stopped_propagation = True


def _pretty_name(listener: Listener) -> str:
    """Name a lazy listener after what it built into, or after itself until it has built."""
    if isinstance(listener, LazyListener):
        return repr(listener) if listener.resolved is None else listener_name(listener.resolved)

    return listener_name(listener)
