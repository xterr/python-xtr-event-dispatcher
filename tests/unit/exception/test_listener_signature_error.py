from __future__ import annotations

from xtr_event_dispatcher import ListenerSignatureError


def test_it_is_a_type_error() -> None:
    assert isinstance(ListenerSignatureError("listener", "(a, b, c, d)"), TypeError)


def test_it_names_the_listener_and_its_parameters() -> None:
    error = ListenerSignatureError("listener", "(a, b, c, d)")

    assert str(error).startswith("listener(a, b, c, d) cannot be a listener")
