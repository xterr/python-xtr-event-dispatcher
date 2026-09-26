from __future__ import annotations

import pytest

from xtr_event_dispatcher._ordering import ordering_targets, target_name


class _Mailer:
    def on_placed(self) -> None: ...


def test_a_single_target_is_read_as_one() -> None:
    assert ordering_targets("app:x", ValueError) == ("app:x",)


def test_nothing_declared_is_no_target() -> None:
    assert ordering_targets(None, ValueError) == ()


def test_an_invalid_target_raises_the_readers_error() -> None:
    with pytest.raises(LookupError):
        _ = ordering_targets([1], LookupError)


def test_a_class_and_a_method_are_named_where_they_are_defined() -> None:
    assert target_name(_Mailer) == f"{__name__}:_Mailer"
    assert target_name(_Mailer.on_placed) == f"{__name__}:_Mailer.on_placed"


def test_a_callable_object_is_no_target() -> None:
    class Callable:
        def __call__(self) -> None: ...

    with pytest.raises(LookupError):
        _ = ordering_targets(Callable(), LookupError)
