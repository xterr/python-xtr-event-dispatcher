from __future__ import annotations

import pytest

from xtr_event_dispatcher import InvalidListenerError
from xtr_event_dispatcher.bundle._declared_listeners import DeclaredListener
from xtr_event_dispatcher.bundle._listener_ordering import ordered
from xtr_event_dispatcher.bundle._listener_reference import ServiceListener


def _declared(
    name: str,
    priority: int | None = None,
    *,
    before: tuple[str, ...] = (),
    after: tuple[str, ...] = (),
) -> DeclaredListener:
    return DeclaredListener(
        ServiceListener(object, None, name),
        "foo",
        priority,
        None,
        before,
        after,
        (f"app:{name}",),
    )


def _methods(result: tuple[tuple[int, object], ...]) -> list[tuple[int, str]]:
    pairs: list[tuple[int, str]] = []
    for priority, reference in result:
        assert isinstance(reference, ServiceListener)
        pairs.append((priority, reference.method))
    return pairs


def test_without_constraints_the_declared_order_and_priorities_stay() -> None:
    result = ordered("foo", [_declared("a"), _declared("b", 5)])

    assert _methods(result) == [(0, "a"), (5, "b")]


def test_a_listener_without_priority_moves_after_its_target() -> None:
    result = ordered("foo", [_declared("a", after=("app:b",)), _declared("b")])

    assert _methods(result) == [(0, "b"), (0, "a")]


def test_a_target_nothing_declares_is_ignored() -> None:
    result = ordered("foo", [_declared("a", before=("elsewhere:x",))])

    assert _methods(result) == [(0, "a")]


def test_a_cycle_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="cannot be met"):
        _ = ordered("foo", [_declared("a", before=("app:b",)), _declared("b", before=("app:a",))])


def test_a_listener_declared_twice_is_ordered_as_two() -> None:
    result = ordered("foo", [_declared("a"), _declared("a"), _declared("b", before=("app:a",))])

    assert _methods(result) == [(0, "b"), (0, "a"), (0, "a")]
