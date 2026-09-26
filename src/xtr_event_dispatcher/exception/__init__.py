"""Every error this library raises.

All of them derive from :class:`EventDispatcherError`, so one ``except``
catches anything dispatching can go wrong with, and a narrower one handles a
single cause. An exception raised by a listener is not one of them: it
reaches the code that dispatched the event unchanged.
"""

from __future__ import annotations

from .argument_not_found_error import ArgumentNotFoundError
from .bad_method_call_error import BadMethodCallError
from .event_dispatcher_error import EventDispatcherError
from .invalid_argument_error import InvalidArgumentError
from .invalid_listener_error import InvalidListenerError
from .invalid_subscriber_error import InvalidSubscriberError
from .listener_signature_error import ListenerSignatureError

__all__ = [
    "ArgumentNotFoundError",
    "BadMethodCallError",
    "EventDispatcherError",
    "InvalidArgumentError",
    "InvalidListenerError",
    "InvalidSubscriberError",
    "ListenerSignatureError",
]
