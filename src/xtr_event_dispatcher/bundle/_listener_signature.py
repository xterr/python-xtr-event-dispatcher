"""Reading a listener's signature: its event, its method, and what it takes itself.

A declared listener names its event and method only when it has to; the
rest is read here from the class and the annotations, while the container is
built, so that a listener no dispatcher could call fails the build.
"""

from __future__ import annotations

import inspect
import re
import types
from collections.abc import Callable
from typing import Annotated, cast, get_args, get_origin, get_type_hints

from xtr_dependency_injection import is_container_supplied
from xtr_event_dispatcher_contracts import Event, event_name_of

from xtr_event_dispatcher._listener_call import signature_arity
from xtr_event_dispatcher._ordering import target_name
from xtr_event_dispatcher.exception import InvalidListenerError, ListenerSignatureError

__all__ = [
    "CALL",
    "check_method",
    "default_method",
    "events_of",
    "function_of",
    "function_of_or_none",
    "own_arity",
]

CALL = "__call__"


def default_method(owner: type, event: str | type) -> str:
    """Return ``on_<event>`` when the class has it, else ``__call__``."""
    name = event.__name__ if isinstance(event, type) else event
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    method = "on_" + re.sub(r"[^0-9A-Za-z]+", "_", snake).strip("_").lower()
    if inspect.getattr_static(owner, method, None) is not None:
        return method
    if function_of_or_none(owner, CALL) is not None:
        return CALL

    raise InvalidListenerError(
        target_name(owner),
        f'it has neither "{method}" nor "__call__" to call for the event "{event_name_of(event)}": '
        f"name one with @as_event_listener(method=...)",
    )


def check_method(owner: type, method: str, label: str) -> None:
    """Refuse a method the class lacks, or one no dispatcher can call."""
    if not callable(getattr(owner, method, None)):
        raise InvalidListenerError(label, f"{owner.__qualname__} has no method {method!r}")
    found = function_of_or_none(owner, method)
    if found is None:
        return

    function, bound = found
    parameters = list(inspect.signature(function).parameters.values())[1 if bound else 0 :]
    try:
        _ = signature_arity(inspect.Signature(parameters), label)
    except ListenerSignatureError as error:
        raise InvalidListenerError(label, str(error)) from error


def function_of(owner: type, method: str) -> tuple[Callable[..., object], bool]:
    """Return the function behind ``method``, and whether its first parameter is bound."""
    found = function_of_or_none(owner, method)
    if found is None:
        raise InvalidListenerError(
            f"{target_name(owner)}.{method}",
            f"{owner.__qualname__} has no method {method!r} to read its event from",
        )

    return found


def function_of_or_none(owner: type, method: str) -> tuple[Callable[..., object], bool] | None:
    """Return the function behind ``method``, and whether ``self`` or ``cls`` is bound to it.

    ``None`` when ``method`` is not a function written on the class or its
    bases.
    """
    found = cast("object", inspect.getattr_static(owner, method, None))
    function = (
        cast("object", found.__func__) if isinstance(found, staticmethod | classmethod) else found
    )
    if not inspect.isfunction(function):
        return None

    return function, not isinstance(found, staticmethod)


def events_of(
    function: Callable[..., object],
    label: str,
    *,
    skip_first: bool = False,
) -> list[str | type]:
    """Read the events a listener takes from its first own parameter's annotation."""
    hints = _hints_of(function, label)
    parameters = list(inspect.signature(function).parameters.values())[1 if skip_first else 0 :]
    own = [p for p in parameters if not is_container_supplied(hints.get(p.name))]
    annotation = hints.get(own[0].name) if own else None
    if get_origin(annotation) is Annotated:
        annotation = cast("object", get_args(annotation)[0])
    origin = get_origin(annotation)
    # ``A | B``, and the ``Union[A, B]`` / ``Optional[A]`` spelling, which has its own origin.
    union = origin is types.UnionType or repr(origin) == "typing.Union"
    members = cast("tuple[object, ...]", get_args(annotation)) if union else (annotation,)
    events: list[str | type] = [
        member
        for member in members
        if isinstance(member, type) and member.__module__ != "builtins" and member is not Event
    ]
    if not events:
        raise InvalidListenerError(
            label,
            "it declares no event: pass one to @as_event_listener, or annotate its first "
            "parameter with the event's class",
        )

    return events


def own_arity(function: Callable[..., object], label: str) -> int:
    """Count the arguments a function takes itself, the ones the container fills left aside.

    The dispatcher passes its arguments by position, so the function's own
    parameters must come first.
    """
    hints = _hints_of(function, label)
    parameters = list(inspect.signature(function).parameters.values())
    supplied = [is_container_supplied(hints.get(p.name)) for p in parameters]
    own = [p for p, filled in zip(parameters, supplied, strict=True) if not filled]
    if parameters[: len(own)] != own:
        raise InvalidListenerError(
            label,
            "the parameters the container fills must come after the event, its name and the "
            "dispatcher",
        )

    try:
        return signature_arity(inspect.Signature(own), label)
    except ListenerSignatureError as error:
        raise InvalidListenerError(label, str(error)) from error


def _hints_of(function: Callable[..., object], label: str) -> dict[str, object]:
    try:
        return get_type_hints(function, include_extras=True)
    except (NameError, TypeError) as error:
        raise InvalidListenerError(
            label,
            f"its annotations cannot be read at runtime ({error}); import what they name "
            f"outside TYPE_CHECKING",
        ) from error
