"""One listener a subscriber declares, spelled out key by key."""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypeAlias, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["OrderTarget", "SubscribedListener"]

OrderTarget: TypeAlias = "str | type | Callable[..., object]"
"""A listener another one runs before or after.

A class names every listener it provides, a function or method names that
one listener, and a ``"module:Qualified.name"`` string names either without
importing it — so a target from a package that is not installed is simply
ignored. A callable object is refused: it has no name of its own to match.
"""


class SubscribedListener(TypedDict):
    """A subscriber's listener, with its priority and ordering spelled out.

    ```python
    {"method": "on_order_placed", "priority": 10, "after": [AuditSubscriber]}
    ```

    ``before`` and ``after`` place the listener relative to others. A
    dispatcher on its own cannot honour them — it does not know the other
    listeners' owners — so it requires a ``priority`` beside them; a
    container, which sees every listener at once, orders by them.
    """

    method: str
    priority: NotRequired[int]
    before: NotRequired[OrderTarget | Sequence[OrderTarget]]
    after: NotRequired[OrderTarget | Sequence[OrderTarget]]
