from __future__ import annotations

import pytest

from xtr_event_dispatcher import ArgumentNotFoundError, GenericEvent


class _Subject:
    pass


@pytest.fixture
def subject() -> _Subject:
    return _Subject()


@pytest.fixture
def event(subject: _Subject) -> GenericEvent:
    return GenericEvent(subject, {"name": "Event"})


def test_events_with_the_same_subject_and_arguments_are_equal(
    event: GenericEvent,
    subject: _Subject,
) -> None:
    assert event == GenericEvent(subject, {"name": "Event"})


def test_a_stopped_event_differs_from_a_running_one(event: GenericEvent, subject: _Subject) -> None:
    event.stop_propagation()

    assert event != GenericEvent(subject, {"name": "Event"})


def test_an_event_is_not_equal_to_a_mapping_of_its_arguments(event: GenericEvent) -> None:
    assert event != {"name": "Event"}


def test_it_returns_every_argument(event: GenericEvent) -> None:
    assert event.get_arguments() == {"name": "Event"}


def test_setting_arguments_replaces_them_all(event: GenericEvent) -> None:
    result = event.set_arguments({"foo": "bar"})

    assert event.get_arguments() == {"foo": "bar"}
    assert result is event


def test_setting_an_argument_keeps_the_others(event: GenericEvent) -> None:
    result = event.set_argument("foo2", "bar2")

    assert event.get_arguments() == {"name": "Event", "foo2": "bar2"}
    assert result is event


def test_it_returns_an_argument_by_name(event: GenericEvent) -> None:
    assert event.get_argument("name") == "Event"


def test_an_unknown_argument_is_an_error(event: GenericEvent) -> None:
    with pytest.raises(ArgumentNotFoundError) as raised:
        _ = event.get_argument("nameNotExist")

    assert raised.value.key == "nameNotExist"


def test_an_argument_reads_by_subscript(event: GenericEvent) -> None:
    assert event["name"] == "Event"


def test_an_unknown_argument_by_subscript_is_a_key_error(event: GenericEvent) -> None:
    with pytest.raises(KeyError):
        _ = event["nameNotExist"]


def test_an_argument_writes_by_subscript(event: GenericEvent) -> None:
    event["foo2"] = "bar2"

    assert event.get_arguments() == {"name": "Event", "foo2": "bar2"}


def test_an_argument_is_deleted_by_subscript(event: GenericEvent) -> None:
    del event["name"]

    assert event.get_arguments() == {}


def test_deleting_an_unknown_argument_is_a_key_error(event: GenericEvent) -> None:
    with pytest.raises(KeyError):
        del event["nameNotExist"]


def test_membership_tells_which_arguments_exist(event: GenericEvent) -> None:
    assert "name" in event
    assert "nameNotExist" not in event


def test_has_argument_tells_which_arguments_exist(event: GenericEvent) -> None:
    assert event.has_argument("name")
    assert not event.has_argument("nameNotExist")


def test_it_returns_its_subject(event: GenericEvent, subject: _Subject) -> None:
    assert event.get_subject() is subject


def test_iterating_gives_the_arguments(event: GenericEvent) -> None:
    assert dict(event.items()) == {"name": "Event"}
    assert len(event) == 1


def test_the_arguments_given_are_copied(subject: _Subject) -> None:
    arguments: dict[str, object] = {"name": "Event"}
    event = GenericEvent(subject, arguments)

    arguments["later"] = True

    assert event.get_arguments() == {"name": "Event"}


def test_its_representation_shows_the_subject_and_the_arguments() -> None:
    assert (
        repr(GenericEvent("order", {"notify": True})) == "GenericEvent('order', {'notify': True})"
    )
