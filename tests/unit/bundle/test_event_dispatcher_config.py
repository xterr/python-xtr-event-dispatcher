from __future__ import annotations

from typing import cast

import pytest

from xtr_event_dispatcher import Event, InvalidArgumentError
from xtr_event_dispatcher.bundle import EventDispatcherConfig


class _Placed(Event):
    pass


def test_it_builds_with_no_arguments() -> None:
    config = EventDispatcherConfig()

    assert config.dispatchers == ()
    assert config.aliases() == {}
    assert config.trace is None


def test_aliases_are_read_as_event_names() -> None:
    config = EventDispatcherConfig(event_aliases={"placed": _Placed})

    assert config.aliases() == {"placed": f"{__name__}._Placed"}


@pytest.mark.parametrize("dispatchers", [("",), ("audit", "audit")], ids=["empty", "twice"])
def test_a_bad_dispatcher_name_is_refused(dispatchers: tuple[str, ...]) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EventDispatcherConfig(dispatchers=dispatchers)


def test_an_alias_that_is_not_a_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = EventDispatcherConfig(event_aliases={"placed": cast("type", cast("object", 5))})
