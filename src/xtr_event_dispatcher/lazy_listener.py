"""A listener whose object is built the first time it is needed."""

from __future__ import annotations

import asyncio
import threading
import weakref
from typing import TYPE_CHECKING, ClassVar, cast, override

from ._listener_call import call_listener, positional_arity

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_event_dispatcher_contracts import Listener

__all__ = ["LazyListener"]

_CALL = "__call__"

# Guards the creation of each listener's per-loop build lock: loops in other
# threads may ask for theirs at the same moment.
_LOCKS_GUARD = threading.Lock()


class LazyListener:
    """A method of an object that is only built when an event needs it.

    Registering a listener usually means building the object it belongs to —
    and whatever that object needs — for an event that may never be
    dispatched. A lazy listener holds a factory instead, awaited the first
    time the listener is about to run; the method it names is then bound to
    what the factory returned, and that binding is kept.

    ```python
    dispatcher.add_listener(OrderPlaced, LazyListener(build_mailer, "on_order_placed"))
    ```

    A dispatcher replaces a lazy listener with the bound method once it has
    been built, so both identify it afterwards — to remove it, or to ask for
    its priority. Until then, only the lazy listener itself does.

    Dispatches arriving together on one event loop before the first build
    share it: the first awaits the factory and the others wait for it. Each
    event loop builds under a lock of its own, so a listener kept for the
    whole process serves every loop; loops running in different threads may
    each await the factory once, the first result is kept and the others
    discarded, so a factory should hand out a shared object, as a container
    does.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_arity", "_factory", "_locks", "_method", "_resolved")

    _arity: int
    _factory: Callable[[], Awaitable[object]]
    _locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]
    _method: str
    _resolved: Listener | None

    def __init__(self, factory: Callable[[], Awaitable[object]], method: str = _CALL) -> None:
        """Hold the factory and the method to call on what it builds.

        Args:
            factory: Builds, or fetches, the object the listener belongs to.
            method: The method to call on it; ``"__call__"`` calls the object
                itself.
        """
        self._factory = factory
        self._method = method
        self._resolved = None
        # Read once the listener is built: a built listener keeps its signature.
        self._arity = 0
        self._locks = weakref.WeakKeyDictionary()

    @property
    def method(self) -> str:
        """The method called on the object the factory returns."""
        return self._method

    @property
    def resolved(self) -> Listener | None:
        """The bound listener, once built; ``None`` before."""
        return self._resolved

    async def resolve(self) -> Listener:
        """Build the object on the first call, and return the listener bound to it.

        With ``"__call__"`` for method, the listener is the object itself, so
        it is the object that identifies the listener afterwards.
        """
        resolved = self._resolved
        if resolved is not None:
            return resolved

        async with self._build_lock():
            resolved = self._resolved
            if resolved is None:
                built = await self._factory()
                # A loop in another thread may have built it meanwhile: keep the first.
                resolved = self._resolved
                if resolved is None:
                    resolved = cast(
                        "Listener",
                        built if self._method == _CALL else getattr(built, self._method),
                    )
                    self._arity = positional_arity(resolved)
                    self._resolved = resolved
        # Built: every later call returns above, so no loop needs its lock any
        # more — and a lock first waited on keeps its loop alive, so it goes.
        with _LOCKS_GUARD:
            self._locks.clear()

        return resolved

    def _build_lock(self) -> asyncio.Lock:
        """Return the lock the running event loop builds this listener under.

        An :class:`asyncio.Lock` belongs to the loop it is first waited on, so
        one shared by every loop would refuse the second; each loop gets its
        own, dropped with the loop.
        """
        loop = asyncio.get_running_loop()
        with _LOCKS_GUARD:
            lock = self._locks.get(loop)
            if lock is None:
                lock = self._locks[loop] = asyncio.Lock()

        return lock

    async def __call__(self, *arguments: object) -> None:
        """Build the listener if needed, and call it as a dispatcher would.

        Takes the event, its name and the dispatcher, and passes on as many
        as the built listener takes.
        """
        listener = await self.resolve()
        await call_listener(listener, self._arity, arguments)

    @override
    def __repr__(self) -> str:
        """Name the factory and the method, which is all there is to know before the build."""
        factory: object = getattr(self._factory, "__qualname__", self._factory)
        return f"LazyListener({factory}, {self._method!r})"
