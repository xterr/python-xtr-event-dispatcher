"""Listener objects the dispatcher tests register, recording how they were called."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

if TYPE_CHECKING:
    from xtr_event_dispatcher import Event

__all__ = ["DispatcherRecorder", "RecordingListener"]


@final
class RecordingListener:
    """Records which of its methods ran; ``post_foo`` stops an event ``pre_foo`` did not see."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.pre_foo_invoked = False
        self.post_foo_invoked = False

    def pre_foo(self, event: Event) -> None:
        del event
        self.pre_foo_invoked = True

    def post_foo(self, event: Event) -> None:
        self.post_foo_invoked = True
        if not self.pre_foo_invoked:
            event.stop_propagation()

    def __call__(self) -> None:
        pass


@final
class DispatcherRecorder:
    """Records the name and the dispatcher a listener is called with."""

    def __init__(self, name: str = "") -> None:
        self.label = name
        self.name: str | None = None
        self.dispatcher: object | None = None
        self.invoked = False

    def foo(self, event: object, event_name: str, dispatcher: object) -> None:
        del event
        self.name = event_name
        self.dispatcher = dispatcher

    def __call__(self, event: object, event_name: str, dispatcher: object) -> None:
        del event
        self.name = event_name
        self.dispatcher = dispatcher
        self.invoked = True

    @override
    def __repr__(self) -> str:
        return f"DispatcherRecorder({self.label!r})"
