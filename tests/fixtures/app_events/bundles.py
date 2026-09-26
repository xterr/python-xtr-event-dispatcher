from __future__ import annotations

from tests.fixtures.qualified_audit import QualifiedAuditBundle
from xtr_event_dispatcher.bundle import EventDispatcherBundle

BUNDLES = {EventDispatcherBundle: {"all": True}, QualifiedAuditBundle: {"all": True}}
