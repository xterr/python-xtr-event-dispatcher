"""How a dispatcher calls a listener: with as many of its three arguments as it takes."""

from __future__ import annotations

import inspect
from inspect import Parameter
from typing import TYPE_CHECKING, cast

from ._naming import listener_name
from .exception import ListenerSignatureError

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

__all__ = ["call_listener", "positional_arity", "signature_arity"]

_ARGUMENTS = 3
"""The event, the name it was dispatched under, and the dispatcher."""


def positional_arity(listener: Listener) -> int:
    """Return how many of the event, its name and the dispatcher ``listener`` takes.

    A listener takes them by position, and as many as it declares: one that
    only cares about the event declares one parameter, one that ignores it
    declares none. One taking ``*args`` gets all three.

    Raises:
        ListenerSignatureError: When the listener requires more than three
            positional arguments, or a keyword-only one.
    """
    try:
        signature = inspect.signature(listener)
    except ValueError:
        # Some callables implemented in C publish no signature. Nothing says
        # how many arguments they take, so they are given every one.
        return _ARGUMENTS

    return signature_arity(signature, listener_name(listener))


def signature_arity(signature: inspect.Signature, name: str) -> int:
    """Return how many of the three arguments a listener with ``signature`` takes.

    For a caller that knows better than :func:`inspect.signature` which
    parameters are the listener's own — a container dropping those it fills.

    Raises:
        ListenerSignatureError: As :func:`positional_arity`, naming ``name``.
    """
    positional = 0
    required = 0
    variadic = False
    for parameter in signature.parameters.values():
        match parameter.kind:
            case Parameter.POSITIONAL_ONLY | Parameter.POSITIONAL_OR_KEYWORD:
                positional += 1
                if _is_required(parameter):
                    required += 1
            case Parameter.VAR_POSITIONAL:
                variadic = True
            case Parameter.KEYWORD_ONLY:
                if _is_required(parameter):
                    raise ListenerSignatureError(name, _parameters_of(signature))
            case Parameter.VAR_KEYWORD:
                pass

    if required > _ARGUMENTS:
        raise ListenerSignatureError(name, _parameters_of(signature))

    return _ARGUMENTS if variadic else min(positional, _ARGUMENTS)


async def call_listener(
    listener: Listener,
    arity: int,
    arguments: tuple[object, ...],
) -> None:
    """Call ``listener`` with the first ``arity`` arguments, awaiting what it returns if needed.

    ``arguments`` are the event, its name and the dispatcher, in that order.
    """
    result = listener(*arguments[:arity])
    if inspect.isawaitable(result):
        await result


def _is_required(parameter: Parameter) -> bool:
    default = cast("object", parameter.default)
    return default is Parameter.empty


def _parameters_of(signature: inspect.Signature) -> str:
    """Render the parameters alone: what they are called and how they are passed is the problem."""
    plain = [
        parameter.replace(annotation=Parameter.empty) for parameter in signature.parameters.values()
    ]
    return str(signature.replace(parameters=plain, return_annotation=Parameter.empty))
