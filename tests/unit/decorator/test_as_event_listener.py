from __future__ import annotations

from typing import cast

import pytest

from xtr_event_dispatcher import InvalidListenerError, as_event_listener
from xtr_event_dispatcher.decorator import EventListenerDeclaration, listeners_declared_on


def _other() -> None: ...


def test_it_returns_what_it_decorates() -> None:
    def listener() -> None: ...

    assert as_event_listener("foo")(listener) is listener


def test_it_records_what_was_declared() -> None:
    @as_event_listener("foo", priority=3, dispatcher="audit", before=_other, after=["x:y"])
    def listener() -> None: ...

    assert listeners_declared_on(listener) == (
        EventListenerDeclaration("foo", None, 3, "audit", (_other,), ("x:y",)),
    )


def test_it_can_be_repeated() -> None:
    @as_event_listener("foo")
    @as_event_listener("bar")
    def listener() -> None: ...

    assert [declaration.event for declaration in listeners_declared_on(listener)] == ["bar", "foo"]


def test_an_ordering_target_that_is_no_listener_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="neither a class, a function"):

        @as_event_listener("foo", before=cast("list[str]", [5]))
        def listener() -> None: ...
