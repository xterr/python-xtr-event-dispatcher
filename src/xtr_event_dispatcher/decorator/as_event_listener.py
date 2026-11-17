"""Declaring, on the listener itself, which event it listens to."""

from __future__ import annotations

from types import FunctionType
from typing import TYPE_CHECKING, TypeVar, cast, overload

from xtr_event_dispatcher._ordering import describe_invalid_target, ordering_targets, target_name
from xtr_event_dispatcher.exception import InvalidListenerError

from .event_listener_declaration import LISTENERS_ATTRIBUTE, EventListenerDeclaration, recorded_on

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_event_dispatcher.subscribed_listener import OrderTarget

__all__ = ["as_event_listener"]

_ListenerT = TypeVar("_ListenerT", bound="Callable[..., object] | type")
_FunctionT = TypeVar("_FunctionT", bound="Callable[..., object]")
_DeclaredT = TypeVar("_DeclaredT")

# What ``@as_event_listener`` written bare is handed: never an event, which is a
# name or a class, so a class is only ever declared a listener with parentheses.
_BARE_TARGETS = (FunctionType, staticmethod, classmethod)


@overload
def as_event_listener(
    event: str | type | None = None,
    *,
    method: str | None = None,
    priority: int | None = None,
    dispatcher: str | None = None,
    before: OrderTarget | Sequence[OrderTarget] | None = None,
    after: OrderTarget | Sequence[OrderTarget] | None = None,
) -> Callable[[_ListenerT], _ListenerT]: ...


@overload
def as_event_listener(event: _FunctionT, /) -> _FunctionT: ...


def as_event_listener(  # noqa: PLR0913 — one argument per thing a listener can declare.
    event: str | type | Callable[..., object] | None = None,
    *,
    method: str | None = None,
    priority: int | None = None,
    dispatcher: str | None = None,
    before: OrderTarget | Sequence[OrderTarget] | None = None,
    after: OrderTarget | Sequence[OrderTarget] | None = None,
) -> Callable[[_ListenerT], _ListenerT] | Callable[..., object]:
    """Declare the decorated class, method or function a listener, for a container to register.

    It only records the declaration: the event dispatcher bundle reads it and
    registers the listener, building a class only when an event it listens to
    is dispatched. Without a container, register listeners with
    :meth:`~xtr_event_dispatcher.event_dispatcher.EventDispatcher.add_listener`.

    ```python
    @as_event_listener()
    async def send_receipt(event: OrderPlaced, mailer: Injected[Mailer]) -> None: ...


    class Stock:
        @as_event_listener(priority=10)
        def on_order_placed(self, event: OrderPlaced) -> None: ...


    @as_event_listener(OrderShipped, method="notify", after=Stock)
    class Notifier:
        def notify(self, event: OrderShipped) -> None: ...
    ```

    The decorator can be repeated to listen to several events. On a function
    or a method declaring nothing beyond its event's annotation, it may be
    written bare, ``@as_event_listener``; a class always takes the
    parentheses, since a class given first is the event to listen to.

    Args:
        event: The event to listen to, as a name or a class. Without it, the
            type the listener's first parameter is annotated with is the
            event — each member of a union too.
        method: On a class, the method to call. Without it, ``on_<event>``
            — ``on_order_placed`` for ``OrderPlaced`` or ``"order.placed"`` —
            and ``__call__`` when there is no such method.
        priority: Higher runs earlier. Without it, ``before``/``after`` place
            the listener, at ``0`` when they allow it.
        dispatcher: The named dispatcher to listen on, rather than the
            default one.
        before: Listeners — classes, functions or methods, or
            ``"module:Qualified.name"`` strings — this one runs before.
        after: Listeners this one runs after.

    Raises:
        InvalidListenerError: When ``before`` or ``after`` names something
            that is not a listener.
    """
    if isinstance(event, _BARE_TARGETS):
        return _declared(event, EventListenerDeclaration(None, None, None, None, (), ()))

    def decorate(listener: _ListenerT) -> _ListenerT:
        name = target_name(listener)

        def invalid(target: object) -> InvalidListenerError:
            return InvalidListenerError(name, describe_invalid_target(target))

        return _declared(
            listener,
            EventListenerDeclaration(
                cast("str | type | None", event),
                method,
                priority,
                dispatcher,
                ordering_targets(before, invalid),
                ordering_targets(after, invalid),
            ),
        )

    return decorate


def _declared(listener: _DeclaredT, declaration: EventListenerDeclaration) -> _DeclaredT:
    """Record ``declaration`` on ``listener``, and return it as it was."""
    # Above ``@staticmethod`` or ``@classmethod``, record on the function
    # they wrap, where the reader looks whichever way round they are.
    target: object = getattr(listener, "__func__", listener)
    setattr(target, LISTENERS_ATTRIBUTE, (*recorded_on(target), declaration))
    return listener
