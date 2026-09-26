from __future__ import annotations

from xtr_event_dispatcher import InvalidListenerError


def test_it_is_a_value_error() -> None:
    assert isinstance(InvalidListenerError("app:listener", "no event"), ValueError)


def test_it_names_the_listener_and_the_reason() -> None:
    assert (
        str(InvalidListenerError("app:listener", "no event")) == "Listener app:listener: no event"
    )
