from __future__ import annotations

import pytest

from xtr_event_dispatcher import InvalidListenerError, as_event_listener
from xtr_event_dispatcher.decorator import EventListenerDeclaration, listeners_declared_on
from xtr_event_dispatcher.decorator.event_listener_declaration import LISTENERS_ATTRIBUTE


@as_event_listener("placed", method="handle")
class _Base:
    @as_event_listener("shipped")
    def on_shipped(self) -> None: ...

    def handle(self) -> None: ...


class _Child(_Base):
    @as_event_listener("cancelled", priority=2)
    def on_cancelled(self) -> None: ...


def test_a_class_lists_its_own_declarations_then_its_methods() -> None:
    assert listeners_declared_on(_Base) == (
        EventListenerDeclaration("placed", "handle"),
        EventListenerDeclaration("shipped", "on_shipped"),
    )


def test_a_subclass_inherits_method_declarations_but_not_class_ones() -> None:
    assert listeners_declared_on(_Child) == (
        EventListenerDeclaration("cancelled", "on_cancelled", 2),
        EventListenerDeclaration("shipped", "on_shipped"),
    )


def test_an_undecorated_object_declares_nothing() -> None:
    assert listeners_declared_on(object()) == ()


class _Explicit:
    @as_event_listener("placed", method="handle")
    def on_placed(self) -> None: ...

    def handle(self) -> None: ...


def test_a_declaration_on_a_method_naming_another_method_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="cannot name another method"):
        _ = listeners_declared_on(_Explicit)


class _Static:
    @staticmethod
    @as_event_listener("placed")
    def below() -> None: ...

    @as_event_listener("shipped")
    @classmethod
    def above(cls) -> None: ...


def test_static_and_class_methods_are_read_whichever_way_round() -> None:
    assert listeners_declared_on(_Static) == (
        EventListenerDeclaration("placed", "below"),
        EventListenerDeclaration("shipped", "above"),
    )


def test_a_foreign_attribute_value_declares_nothing() -> None:
    def listener() -> None: ...

    setattr(listener, LISTENERS_ATTRIBUTE, "not declarations")

    assert listeners_declared_on(listener) == ()
