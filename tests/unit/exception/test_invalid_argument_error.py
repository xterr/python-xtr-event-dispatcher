from __future__ import annotations

from xtr_event_dispatcher import InvalidArgumentError


def test_it_is_a_value_error_carrying_its_reason() -> None:
    error = InvalidArgumentError("bad")

    assert isinstance(error, ValueError)
    assert error.reason == "bad"
