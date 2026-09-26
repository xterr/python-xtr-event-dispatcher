from __future__ import annotations

from xtr_event_dispatcher import InvalidSubscriberError


def test_it_is_a_value_error() -> None:
    assert isinstance(InvalidSubscriberError("Mailer", "order.placed", "no method"), ValueError)


def test_it_names_the_declaration_and_the_reason() -> None:
    error = InvalidSubscriberError("Mailer", "order.placed", "no method")

    assert str(error) == 'Mailer.get_subscribed_events() for event "order.placed": no method'


def test_a_mistake_about_no_event_names_none() -> None:
    error = InvalidSubscriberError("Mailer", None, "not a mapping")

    assert str(error) == "Mailer.get_subscribed_events(): not a mapping"
