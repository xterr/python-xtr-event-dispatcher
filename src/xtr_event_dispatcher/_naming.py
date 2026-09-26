"""One way to name a listener, for traces and error messages alike."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import Listener

__all__ = ["listener_name"]


def listener_name(listener: Listener) -> str:
    """Name ``listener`` the way a person looking for it in the code would.

    A method is its object's class and its name, a function or a class its
    qualified name, a callable object its class and ``__call__`` — each after
    the module it comes from.
    """
    if inspect.ismethod(listener):
        return f"{_qualified(type(listener.__self__))}.{listener.__name__}"
    if inspect.isroutine(listener) or isinstance(listener, type):
        return _qualified(listener)

    return f"{_qualified(type(listener))}.__call__"


def _qualified(target: object) -> str:
    module: object = getattr(target, "__module__", None)
    qualname: object = getattr(target, "__qualname__", None) or getattr(target, "__name__", "?")
    return f"{module}.{qualname}" if module else str(qualname)
