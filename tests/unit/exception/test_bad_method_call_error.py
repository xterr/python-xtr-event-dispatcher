from __future__ import annotations

from xtr_event_dispatcher import BadMethodCallError


def test_it_is_a_runtime_error() -> None:
    assert isinstance(BadMethodCallError("add_listener"), RuntimeError)


def test_it_names_the_method_and_the_way_out() -> None:
    assert str(BadMethodCallError("add_listener")) == (
        "add_listener() cannot be called: this event dispatcher cannot be modified; "
        "add the listener to a ScopedEventDispatcher wrapping it instead."
    )
