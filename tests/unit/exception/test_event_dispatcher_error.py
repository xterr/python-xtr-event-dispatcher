from __future__ import annotations

import pytest

from xtr_event_dispatcher import (
    ArgumentNotFoundError,
    BadMethodCallError,
    EventDispatcherError,
    InvalidArgumentError,
    InvalidListenerError,
    InvalidSubscriberError,
    ListenerSignatureError,
)


@pytest.mark.parametrize(
    "error",
    [
        ArgumentNotFoundError,
        BadMethodCallError,
        InvalidArgumentError,
        InvalidListenerError,
        InvalidSubscriberError,
        ListenerSignatureError,
    ],
)
def test_every_error_derives_from_it(error: type[Exception]) -> None:
    assert issubclass(error, EventDispatcherError)
