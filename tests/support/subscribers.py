"""Subscribers declaring their events in every shape ``get_subscribed_events()`` accepts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_event_dispatcher import EventSubscriberInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = [
    "Subscriber",
    "SubscriberWithMultipleListeners",
    "SubscriberWithNamedKeys",
    "SubscriberWithNamedKeysAndMultipleListeners",
    "SubscriberWithOrderingConstraints",
    "SubscriberWithPriorities",
    "SubscriberWithUnprioritizedOrderingConstraint",
    "SubscriberWithUnprioritizedOrderingConstraintInAList",
]


class _Methods:
    def pre_foo(self) -> None: ...

    def pre_foo1(self) -> None: ...

    def pre_foo2(self) -> None: ...

    def pre_foo3(self) -> None: ...

    def post_foo(self) -> None: ...

    def post_foo_too(self) -> None: ...


class Subscriber(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"pre.foo": "pre_foo", "post.foo": "post_foo"}


class SubscriberWithPriorities(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"pre.foo": ("pre_foo", 10), "post.foo": "post_foo"}


class SubscriberWithMultipleListeners(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"pre.foo": ["pre_foo1", ("pre_foo2", 10)]}


class SubscriberWithNamedKeys(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            "pre.foo": {"method": "pre_foo", "priority": 10},
            "post.foo": {"method": "post_foo"},
        }


class SubscriberWithNamedKeysAndMultipleListeners(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            "pre.foo": [
                {"method": "pre_foo1"},
                {"method": "pre_foo2", "priority": 10},
                ("pre_foo3", 20),
            ],
        }


class SubscriberWithOrderingConstraints(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            "pre.foo": {"method": "pre_foo", "priority": 10, "before": "some.listener"},
            "post.foo": [
                {"method": "post_foo", "priority": 0, "after": ["some.listener", "other.listener"]},
                {"method": "post_foo_too", "before": []},
            ],
        }


class SubscriberWithUnprioritizedOrderingConstraint(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"pre.foo": {"method": "pre_foo", "before": "some.listener"}}


class SubscriberWithUnprioritizedOrderingConstraintInAList(_Methods, EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            "post.foo": [("post_foo", 5), {"method": "post_foo_too", "after": "some.listener"}],
        }
