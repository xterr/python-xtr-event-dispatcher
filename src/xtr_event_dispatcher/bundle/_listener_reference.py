"""How to reach each listener of a ``ListenerMap`` once the container runs."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import TypeAlias

from xtr_dependency_injection import bind_callable
from xtr_event_dispatcher_contracts import Listener
from xtr_service_contracts import ContainerInterface

from xtr_event_dispatcher.lazy_listener import LazyListener

__all__ = ["FunctionListener", "ListenerReference", "ServiceListener"]


@dataclass(frozen=True, slots=True)
class ServiceListener:
    """A method of a service, fetched from the container the first time it runs.

    Attributes:
        service: The service's type.
        qualifier: Its qualifier.
        method: The method to call on it.
    """

    service: type[object]
    qualifier: Hashable | None
    method: str

    def listener(self, container: ContainerInterface) -> Listener:
        """Return a lazy listener fetching the service from ``container``."""

        async def fetch() -> object:
            return await container.get(self.service, self.qualifier)

        # Named after the service, so a listener not built yet reads as what it will be.
        qualifier = "" if self.qualifier is None else f"[{self.qualifier!r}]"
        fetch.__qualname__ = f"{self.service.__module__}.{self.service.__qualname__}{qualifier}"

        return LazyListener(fetch, self.method)


@dataclass(frozen=True, slots=True)
class FunctionListener:
    """A function whose container-supplied parameters are filled on every call.

    Attributes:
        function: The function declared a listener.
        arity: How many of the event, its name and the dispatcher it takes
            itself — the parameters the container fills left aside.
    """

    function: Callable[..., object]
    arity: int

    def listener(self, container: ContainerInterface) -> Listener:
        """Return the function bound to ``container``, given only the arguments it takes."""
        bound = bind_callable(container, self.function)
        arity = self.arity

        async def listener(*arguments: object) -> None:
            _ = await bound(*arguments[:arity])

        # Named like the function, for traces; not wrapped, so that its
        # signature stays the one taking every argument.
        for attribute in ("__module__", "__name__", "__qualname__"):
            setattr(listener, attribute, getattr(self.function, attribute))

        return listener


ListenerReference: TypeAlias = ServiceListener | FunctionListener
