"""Declaring listeners where they are written, for a container to register."""

from __future__ import annotations

from .as_event_listener import as_event_listener
from .event_listener_declaration import EventListenerDeclaration, listeners_declared_on

__all__ = ["EventListenerDeclaration", "as_event_listener", "listeners_declared_on"]
