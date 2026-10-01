from __future__ import annotations

from xtr_event_dispatcher.bundle import ListenerMap
from xtr_event_dispatcher.bundle._listener_reference import FunctionListener


def _named(name: str) -> FunctionListener:
    def listener() -> None: ...

    listener.__name__ = name
    return FunctionListener(listener, 0)


_OWN = _named("own")
_OWN_LOW = _named("own_low")
_OTHER = _named("other")
_OTHER_HIGH = _named("other_high")
_UNRELATED = _named("unrelated")


def test_it_interleaves_the_other_maps_listeners_by_priority() -> None:
    own = ListenerMap({"placed": ((5, _OWN), (-5, _OWN_LOW))})
    other = ListenerMap({"placed": ((10, _OTHER_HIGH), (0, _OTHER))})

    merged = own.with_listeners_of(other, ["placed"])

    assert merged.by_event["placed"] == ((10, _OTHER_HIGH), (5, _OWN), (0, _OTHER), (-5, _OWN_LOW))


def test_at_equal_priority_its_own_listeners_run_first() -> None:
    own = ListenerMap({"placed": ((0, _OWN),)})
    other = ListenerMap({"placed": ((0, _OTHER),)})

    merged = own.with_listeners_of(other, ["placed"])

    assert merged.by_event["placed"] == ((0, _OWN), (0, _OTHER))


def test_it_takes_only_the_events_named() -> None:
    own = ListenerMap({})
    other = ListenerMap({"placed": ((0, _OTHER),), "shipped": ((0, _UNRELATED),)})

    merged = own.with_listeners_of(other, ["placed"])

    assert merged.by_event == {"placed": ((0, _OTHER),)}


def test_it_leaves_both_maps_as_they_were() -> None:
    own = ListenerMap({"placed": ((0, _OWN),)})
    other = ListenerMap({"placed": ((0, _OTHER),)})

    _ = own.with_listeners_of(other, ["placed"])

    assert own.by_event == {"placed": ((0, _OWN),)}
    assert other.by_event == {"placed": ((0, _OTHER),)}
