"""The xtr-dependency-injection bundle for xtr-event-dispatcher."""

from __future__ import annotations

from ._declared_listeners import DISPATCHER_TAG, LISTENER_TAG, SUBSCRIBER_TAG
from .event_dispatcher_bundle import EventDispatcherBundle
from .event_dispatcher_config import EventDispatcherConfig
from .event_dispatcher_factory import (
    EVENT_CHANNEL,
    event_dispatcher_factory,
    traceable_event_dispatcher_factory,
)
from .listener_map import ListenerMap
from .register_listeners_pass import RegisterListenersPass

__all__ = [
    "DISPATCHER_TAG",
    "EVENT_CHANNEL",
    "LISTENER_TAG",
    "SUBSCRIBER_TAG",
    "EventDispatcherBundle",
    "EventDispatcherConfig",
    "ListenerMap",
    "RegisterListenersPass",
    "event_dispatcher_factory",
    "traceable_event_dispatcher_factory",
]
