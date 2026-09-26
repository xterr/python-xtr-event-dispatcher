"""Reading ``before``/``after`` targets, and naming them the way the ordering compares them."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from .subscribed_listener import OrderTarget

__all__ = ["describe_invalid_target", "ordering_targets", "target_name"]


def ordering_targets(
    value: object,
    invalid: Callable[[object], Exception],
) -> tuple[OrderTarget, ...]:
    """Read one target, or a list or tuple of them, as a tuple.

    Args:
        value: What was declared.
        invalid: Builds the error to raise for a target that is not one, so
            each reader reports it as its own kind of mistake.
    """
    match value:
        case None:
            return ()
        case list() | tuple():
            items = cast("list[object] | tuple[object, ...]", value)
            return tuple(_target(item, invalid) for item in items)
        case _:
            return (_target(value, invalid),)


def describe_invalid_target(target: object) -> str:
    """Say why ``target`` cannot be ordered against."""
    return (
        f"{target!r} is neither a class, a function or method, nor a "
        f'"module:Qualified.name" string, so nothing can be ordered against it'
    )


def target_name(target: OrderTarget) -> str:
    """Return the ``"module:Qualified.name"`` a target stands for.

    A string already is one; a class or a function is named after where it
    is defined, so ``Mailer.on_placed`` names ``"app.mail:Mailer.on_placed"``
    and ``Mailer`` names ``"app.mail:Mailer"``.
    """
    if isinstance(target, str):
        return target

    module: object = getattr(target, "__module__", None)
    qualname: object = getattr(target, "__qualname__", None)

    return f"{module}:{qualname}"


def _target(value: object, invalid: Callable[[object], Exception]) -> OrderTarget:
    # A callable object has no qualified name of its own, so it could never
    # match a listener: refused rather than silently ignored.
    if isinstance(value, str | type) or inspect.isroutine(value):
        return value

    raise invalid(value)
