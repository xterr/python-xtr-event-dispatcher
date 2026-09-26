from __future__ import annotations

from xtr_event_dispatcher.debug import ListenerInfo


def test_a_listener_that_never_ran_counts_no_call() -> None:
    assert ListenerInfo("foo", 0, "app.listener").calls == 0
