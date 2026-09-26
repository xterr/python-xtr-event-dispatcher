from __future__ import annotations

from xtr_event_dispatcher import ArgumentNotFoundError


def test_it_is_a_key_error() -> None:
    assert isinstance(ArgumentNotFoundError("name"), KeyError)


def test_it_describes_itself_rather_than_quote_its_key() -> None:
    assert str(ArgumentNotFoundError("name")) == 'Argument "name" not found.'
