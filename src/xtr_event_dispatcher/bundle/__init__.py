"""The xtr-dependency-injection bundle for xtr-event-dispatcher."""

from __future__ import annotations

from .event_dispatcher_bundle import EVENT_CHANNEL, EventDispatcherBundle
from .event_dispatcher_config import EventDispatcherConfig

__all__ = ["EVENT_CHANNEL", "EventDispatcherBundle", "EventDispatcherConfig"]
