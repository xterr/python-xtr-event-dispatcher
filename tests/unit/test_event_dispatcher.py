"""The dispatcher's behaviour, checked on the class, a subclass, and a scoped dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override

from tests.support.listeners import DispatcherRecorder, RecordingListener
from tests.support.subscribers import (
    Subscriber,
    SubscriberWithMultipleListeners,
    SubscriberWithNamedKeys,
    SubscriberWithNamedKeysAndMultipleListeners,
    SubscriberWithOrderingConstraints,
    SubscriberWithPriorities,
    SubscriberWithUnprioritizedOrderingConstraint,
    SubscriberWithUnprioritizedOrderingConstraintInAList,
)
from xtr_event_dispatcher import (
    Event,
    EventDispatcher,
    InvalidSubscriberError,
    LazyListener,
    ListenerSignatureError,
    ScopedEventDispatcher,
    event_name_of,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_event_dispatcher import SubscribedEvents

PRE_FOO = "pre.foo"
POST_FOO = "post.foo"
PRE_BAR = "pre.bar"


class _ChildEventDispatcher(EventDispatcher):
    """Adds nothing: a subclass must behave exactly like its base."""


def _scoped() -> EventDispatcher:
    return ScopedEventDispatcher(EventDispatcher())


@pytest.fixture(
    params=[EventDispatcher, _ChildEventDispatcher, _scoped],
    ids=["plain", "child", "scoped"],
)
def dispatcher(request: pytest.FixtureRequest) -> EventDispatcher:
    factory = cast("Callable[[], EventDispatcher]", request.param)
    return factory()


@final
class _Factory:
    """Builds ``built`` for a lazy listener, counting how often it is asked to."""

    def __init__(self, built: object) -> None:
        self.built = built
        self.calls = 0

    async def __call__(self) -> object:
        self.calls += 1
        return self.built


@dataclass
class _OrderPlaced(Event):
    order_id: int


def test_it_starts_without_listeners(dispatcher: EventDispatcher) -> None:
    assert dispatcher.get_listeners() == {}
    assert not dispatcher.has_listeners(PRE_FOO)
    assert not dispatcher.has_listeners(POST_FOO)


def test_added_listeners_are_reported_per_event(dispatcher: EventDispatcher) -> None:
    listener = RecordingListener()

    dispatcher.add_listener(PRE_FOO, listener.pre_foo)
    dispatcher.add_listener(POST_FOO, listener.post_foo)

    assert dispatcher.has_listeners()
    assert dispatcher.has_listeners(PRE_FOO)
    assert dispatcher.has_listeners(POST_FOO)
    assert len(dispatcher.get_listeners(PRE_FOO)) == 1
    assert len(dispatcher.get_listeners(POST_FOO)) == 1
    assert len(dispatcher.get_listeners()) == 2


def test_listeners_of_an_event_come_highest_priority_first(dispatcher: EventDispatcher) -> None:
    first, second, third, fourth = (RecordingListener(name) for name in "1234")

    dispatcher.add_listener(PRE_FOO, first.pre_foo, -10)
    dispatcher.add_listener(PRE_FOO, second.pre_foo, 10)
    dispatcher.add_listener(PRE_FOO, third.pre_foo)
    dispatcher.add_listener(PRE_FOO, fourth.pre_foo, 20)

    assert dispatcher.get_listeners(PRE_FOO) == [
        fourth.pre_foo,
        second.pre_foo,
        third.pre_foo,
        first.pre_foo,
    ]


def test_listeners_of_every_event_come_highest_priority_first(
    dispatcher: EventDispatcher,
) -> None:
    listeners = [RecordingListener(str(number)) for number in range(1, 7)]

    dispatcher.add_listener(PRE_FOO, listeners[0], -10)
    dispatcher.add_listener(PRE_FOO, listeners[1])
    dispatcher.add_listener(PRE_FOO, listeners[2], 10)
    dispatcher.add_listener(POST_FOO, listeners[3], -10)
    dispatcher.add_listener(POST_FOO, listeners[4])
    dispatcher.add_listener(POST_FOO, listeners[5], 10)

    assert dispatcher.get_listeners() == {
        PRE_FOO: [listeners[2], listeners[1], listeners[0]],
        POST_FOO: [listeners[5], listeners[4], listeners[3]],
    }


def test_a_listener_reports_the_priority_it_was_added_at(dispatcher: EventDispatcher) -> None:
    low = RecordingListener()
    default = RecordingListener()

    dispatcher.add_listener(PRE_FOO, low, -10)
    dispatcher.add_listener(PRE_FOO, default)

    assert dispatcher.get_listener_priority(PRE_FOO, low) == -10
    assert dispatcher.get_listener_priority(PRE_FOO, default) == 0
    assert dispatcher.get_listener_priority("pre.bar", default) is None
    assert dispatcher.get_listener_priority(PRE_FOO, lambda: None) is None


@pytest.mark.anyio
async def test_dispatch_runs_only_the_listeners_of_that_event(dispatcher: EventDispatcher) -> None:
    listener = RecordingListener()
    dispatcher.add_listener(PRE_FOO, listener.pre_foo)
    dispatcher.add_listener(POST_FOO, listener.post_foo)

    _ = await dispatcher.dispatch(Event(), PRE_FOO)

    assert listener.pre_foo_invoked
    assert not listener.post_foo_invoked


@pytest.mark.anyio
async def test_dispatch_returns_the_event_it_was_given(dispatcher: EventDispatcher) -> None:
    dispatcher.add_listener(PRE_FOO, RecordingListener().pre_foo)
    event = Event()

    assert await dispatcher.dispatch(event, PRE_FOO) is event
    assert await dispatcher.dispatch(event, "no.listener") is event


@pytest.mark.anyio
async def test_a_function_listening_to_two_events_runs_for_the_one_dispatched(
    dispatcher: EventDispatcher,
) -> None:
    calls: list[None] = []

    def listener() -> None:
        calls.append(None)

    dispatcher.add_listener(PRE_FOO, listener)
    dispatcher.add_listener(POST_FOO, listener)

    _ = await dispatcher.dispatch(Event(), PRE_FOO)

    assert len(calls) == 1


@pytest.mark.anyio
async def test_a_stopped_event_reaches_no_further_listener(dispatcher: EventDispatcher) -> None:
    first = RecordingListener()
    other = RecordingListener()
    dispatcher.add_listener(POST_FOO, first.post_foo, 10)
    dispatcher.add_listener(POST_FOO, other.post_foo)

    _ = await dispatcher.dispatch(Event(), POST_FOO)

    assert first.post_foo_invoked
    assert not other.post_foo_invoked


@pytest.mark.anyio
async def test_dispatch_runs_listeners_highest_priority_first(
    dispatcher: EventDispatcher,
) -> None:
    invoked: list[str] = []
    dispatcher.add_listener(PRE_FOO, lambda: invoked.append("1"), -10)
    dispatcher.add_listener(PRE_FOO, lambda: invoked.append("2"))
    dispatcher.add_listener(PRE_FOO, lambda: invoked.append("3"), 10)

    _ = await dispatcher.dispatch(Event(), PRE_FOO)

    assert invoked == ["3", "2", "1"]


def test_a_removed_listener_is_gone(dispatcher: EventDispatcher) -> None:
    listener = RecordingListener()
    dispatcher.add_listener(PRE_BAR, listener)

    dispatcher.remove_listener(PRE_BAR, listener)

    assert not dispatcher.has_listeners(PRE_BAR)


def test_removing_from_an_event_without_listeners_does_nothing(
    dispatcher: EventDispatcher,
) -> None:
    dispatcher.remove_listener("not.there", RecordingListener())

    assert not dispatcher.has_listeners()


def test_a_subscriber_listens_to_every_event_it_declares(dispatcher: EventDispatcher) -> None:
    dispatcher.add_subscriber(Subscriber())

    assert dispatcher.has_listeners(PRE_FOO)
    assert dispatcher.has_listeners(POST_FOO)


def test_named_keys_give_a_subscriber_its_priorities(dispatcher: EventDispatcher) -> None:
    subscriber = SubscriberWithNamedKeys()

    dispatcher.add_subscriber(subscriber)

    assert dispatcher.get_listener_priority(PRE_FOO, subscriber.pre_foo) == 10
    assert dispatcher.get_listener_priority(POST_FOO, subscriber.post_foo) == 0


def test_named_keys_declare_several_listeners_of_one_event(dispatcher: EventDispatcher) -> None:
    subscriber = SubscriberWithNamedKeysAndMultipleListeners()

    dispatcher.add_subscriber(subscriber)

    assert dispatcher.get_listeners(PRE_FOO) == [
        subscriber.pre_foo3,
        subscriber.pre_foo2,
        subscriber.pre_foo1,
    ]


def test_removing_a_subscriber_with_named_keys_removes_its_listeners(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = SubscriberWithNamedKeys()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners(PRE_FOO)
    assert not dispatcher.has_listeners(POST_FOO)


def test_removing_a_subscriber_removes_each_of_its_named_listeners(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = SubscriberWithNamedKeysAndMultipleListeners()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners(PRE_FOO)


def test_ordering_constraints_beside_a_priority_are_ignored(dispatcher: EventDispatcher) -> None:
    subscriber = SubscriberWithOrderingConstraints()

    dispatcher.add_subscriber(subscriber)

    assert dispatcher.get_listener_priority(PRE_FOO, subscriber.pre_foo) == 10
    assert dispatcher.get_listener_priority(POST_FOO, subscriber.post_foo) == 0
    assert dispatcher.get_listener_priority(POST_FOO, subscriber.post_foo_too) == 0


def test_a_subscriber_with_ordering_constraints_can_be_removed(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = SubscriberWithOrderingConstraints()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners()


def test_ordering_constraints_without_a_priority_are_refused(dispatcher: EventDispatcher) -> None:
    with pytest.raises(InvalidSubscriberError) as raised:
        dispatcher.add_subscriber(SubscriberWithUnprioritizedOrderingConstraint())

    assert raised.value.subscriber == "SubscriberWithUnprioritizedOrderingConstraint"
    assert raised.value.event_name == PRE_FOO
    assert raised.value.reason == (
        'the "before"/"after" keys of \'pre_foo\' need a "priority" when the subscriber is added '
        "with add_subscriber(): they only apply to subscribers a container registers"
    )


def test_ordering_constraints_without_a_priority_are_refused_in_a_list(
    dispatcher: EventDispatcher,
) -> None:
    with pytest.raises(InvalidSubscriberError) as raised:
        dispatcher.add_subscriber(SubscriberWithUnprioritizedOrderingConstraintInAList())

    assert raised.value.event_name == POST_FOO


def test_a_prioritized_subscriber_runs_before_a_default_one(dispatcher: EventDispatcher) -> None:
    prioritized = SubscriberWithPriorities()
    dispatcher.add_subscriber(Subscriber())

    dispatcher.add_subscriber(prioritized)

    listeners = dispatcher.get_listeners(PRE_FOO)
    assert len(listeners) == 2
    assert listeners[0] == prioritized.pre_foo


def test_a_subscriber_declares_several_listeners_in_a_list(dispatcher: EventDispatcher) -> None:
    subscriber = SubscriberWithMultipleListeners()

    dispatcher.add_subscriber(subscriber)

    assert dispatcher.get_listeners(PRE_FOO) == [subscriber.pre_foo2, subscriber.pre_foo1]


def test_removing_a_subscriber_removes_its_listeners(dispatcher: EventDispatcher) -> None:
    subscriber = Subscriber()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners(PRE_FOO)
    assert not dispatcher.has_listeners(POST_FOO)


def test_removing_a_prioritized_subscriber_removes_its_listeners(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = SubscriberWithPriorities()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners(PRE_FOO)


def test_removing_a_subscriber_removes_all_its_listeners_of_an_event(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = SubscriberWithMultipleListeners()
    dispatcher.add_subscriber(subscriber)

    dispatcher.remove_subscriber(subscriber)

    assert not dispatcher.has_listeners(PRE_FOO)


@pytest.mark.anyio
async def test_a_listener_receives_the_event_name_and_the_dispatcher(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    dispatcher.add_listener("test", recorder.foo)

    _ = await dispatcher.dispatch(Event(), "test")

    assert recorder.name == "test"
    assert recorder.dispatcher is dispatcher


def test_removing_an_unrelated_function_keeps_a_callable_object(
    dispatcher: EventDispatcher,
) -> None:
    dispatcher.add_listener("event", RecordingListener())

    dispatcher.remove_listener("event", lambda: None)

    assert dispatcher.has_listeners("event")


def test_removing_the_only_function_leaves_no_listener(dispatcher: EventDispatcher) -> None:
    def listener() -> None: ...

    dispatcher.add_listener("foo", listener)

    dispatcher.remove_listener("foo", listener)

    assert not dispatcher.has_listeners()
    assert dispatcher.get_listeners() == {}


def test_asking_for_one_event_leaves_every_event_empty(dispatcher: EventDispatcher) -> None:
    assert not dispatcher.has_listeners("foo")

    assert not dispatcher.has_listeners()


def test_has_listeners_builds_no_lazy_listener(dispatcher: EventDispatcher) -> None:
    factory = _Factory(DispatcherRecorder())
    dispatcher.add_listener("foo", LazyListener(factory, "on_foo"))

    assert dispatcher.has_listeners()
    assert dispatcher.has_listeners("foo")
    assert factory.calls == 0


@pytest.mark.anyio
async def test_a_lazy_listener_is_built_once_on_its_first_dispatch(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    factory = _Factory(recorder)
    dispatcher.add_listener("foo", LazyListener(factory, "foo"))
    assert factory.calls == 0

    _ = await dispatcher.dispatch(Event(), "foo")
    _ = await dispatcher.dispatch(Event(), "foo")

    assert factory.calls == 1
    assert recorder.name == "foo"
    assert not recorder.invoked


@pytest.mark.anyio
async def test_a_lazy_listener_without_a_method_calls_what_it_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    factory = _Factory(recorder)
    dispatcher.add_listener("bar", LazyListener(factory))

    _ = await dispatcher.dispatch(Event(), "bar")
    _ = await dispatcher.dispatch(Event(), "bar")

    assert recorder.invoked
    assert factory.calls == 1


@pytest.mark.anyio
async def test_removing_a_method_drops_the_lazy_listener_building_into_it(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    dispatcher.add_listener("foo", LazyListener(_Factory(recorder), "foo"))
    dispatcher.remove_listener("foo", recorder.foo)

    _ = await dispatcher.dispatch(Event(), "foo")

    assert recorder.name is None
    assert not dispatcher.has_listeners("foo")


@pytest.mark.anyio
async def test_a_built_lazy_listener_designates_what_it_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    lazy = LazyListener(_Factory(recorder), "foo")
    _ = await lazy.resolve()
    dispatcher.add_listener("foo", recorder.foo)

    dispatcher.remove_listener("foo", lazy)

    assert not dispatcher.has_listeners("foo")


def test_removing_a_function_leaves_lazy_listeners_unbuilt(dispatcher: EventDispatcher) -> None:
    factory = _Factory(DispatcherRecorder())
    dispatcher.add_listener("foo", LazyListener(factory, "foo"))

    def listener() -> None: ...

    dispatcher.add_listener("foo", listener)

    dispatcher.remove_listener("foo", listener)

    assert factory.calls == 0
    assert dispatcher.has_listeners("foo")


def test_removing_a_method_leaves_lazy_listeners_unbuilt(dispatcher: EventDispatcher) -> None:
    recorder = DispatcherRecorder()
    factory = _Factory(recorder)
    other = _Factory(DispatcherRecorder())
    dispatcher.add_listener("foo", LazyListener(factory, "foo"))
    dispatcher.add_listener("foo", LazyListener(other, "foo"))

    dispatcher.remove_listener("foo", recorder.foo)

    assert factory.calls == 0
    assert other.calls == 0


@pytest.mark.anyio
async def test_a_pending_removal_drops_only_the_listener_it_names(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    other = DispatcherRecorder()
    dispatcher.add_listener("foo", LazyListener(_Factory(recorder), "foo"))
    dispatcher.add_listener("foo", LazyListener(_Factory(other), "foo"))
    dispatcher.remove_listener("foo", recorder.foo)

    _ = await dispatcher.dispatch(Event(), "foo")

    assert dispatcher.get_listeners("foo") == [other.foo]


@pytest.mark.anyio
async def test_a_pending_removal_leaves_other_priorities_alone(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()

    def other() -> None: ...

    dispatcher.add_listener("foo", LazyListener(_Factory(recorder), "foo"), 3)
    dispatcher.add_listener("foo", other, 5)
    dispatcher.remove_listener("foo", recorder.foo)

    _ = await dispatcher.dispatch(Event(), "foo")

    assert dispatcher.get_listener_priority("foo", other) == 5
    assert dispatcher.get_listeners("foo") == [other]


@pytest.mark.anyio
async def test_removing_a_subscriber_drops_its_lazy_listener_unbuilt(
    dispatcher: EventDispatcher,
) -> None:
    subscriber = Subscriber()
    factory = _Factory(subscriber)
    dispatcher.add_listener(PRE_FOO, LazyListener(factory, "pre_foo"))

    dispatcher.remove_subscriber(subscriber)

    assert factory.calls == 0
    _ = await dispatcher.dispatch(Event(), PRE_FOO)
    assert not dispatcher.has_listeners(PRE_FOO)


def test_asking_for_a_priority_builds_no_lazy_listener(dispatcher: EventDispatcher) -> None:
    factory = _Factory(DispatcherRecorder())

    def listener() -> None: ...

    dispatcher.add_listener("foo", LazyListener(factory, "foo"), 3)
    dispatcher.add_listener("foo", listener, 5)

    assert dispatcher.get_listener_priority("foo", listener) == 5
    assert factory.calls == 0


@pytest.mark.anyio
async def test_a_lazy_listener_reports_its_priority_before_and_after_being_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    lazy = LazyListener(_Factory(recorder), "foo")
    dispatcher.add_listener("foo", lazy, 3)
    assert dispatcher.get_listener_priority("foo", lazy) == 3

    _ = await dispatcher.dispatch(Event(), "foo")

    assert dispatcher.get_listener_priority("foo", recorder.foo) == 3


@pytest.mark.anyio
async def test_a_built_lazy_listener_finds_the_priority_of_what_it_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    lazy = LazyListener(_Factory(recorder), "foo")
    _ = await lazy.resolve()

    dispatcher.add_listener("foo", recorder.foo, 5)

    assert dispatcher.get_listener_priority("foo", lazy) == 5


@pytest.mark.anyio
async def test_get_listeners_shows_what_a_lazy_listener_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    lazy = LazyListener(_Factory(recorder), "foo")
    dispatcher.add_listener("foo", lazy, 3)
    assert dispatcher.get_listeners("foo") == [lazy]

    _ = await dispatcher.dispatch(Event(), "foo")

    assert dispatcher.get_listeners("foo") == [recorder.foo]


@pytest.mark.anyio
async def test_a_built_lazy_listener_is_added_as_what_it_built(
    dispatcher: EventDispatcher,
) -> None:
    recorder = DispatcherRecorder()
    lazy = LazyListener(_Factory(recorder), "foo")
    _ = await lazy.resolve()

    dispatcher.add_listener("bar", lazy, 3)

    assert dispatcher.get_listeners() == {"bar": [recorder.foo]}


@pytest.mark.anyio
async def test_listeners_a_lazy_listener_adds_while_built_are_sorted_in(
    dispatcher: EventDispatcher,
) -> None:
    first, second, third, fourth = (DispatcherRecorder(name) for name in "1234")

    async def factory() -> object:
        dispatcher.add_listener("foo", third.foo, 5)
        dispatcher.add_listener("foo", fourth.foo)
        return second

    dispatcher.add_listener("foo", first.foo)
    dispatcher.add_listener("foo", LazyListener(factory, "foo"))

    _ = await dispatcher.dispatch(Event(), "foo")

    expected = [third.foo, first.foo, second.foo, fourth.foo]
    assert dispatcher.get_listeners("foo") == expected
    assert dispatcher.get_listeners("foo") == expected


@pytest.mark.anyio
async def test_a_stopped_event_leaves_later_lazy_listeners_unbuilt(
    dispatcher: EventDispatcher,
) -> None:
    listener = RecordingListener()
    factory = _Factory(listener)
    dispatcher.add_listener("foo", listener.post_foo)
    dispatcher.add_listener("foo", LazyListener(factory, "pre_foo"))

    _ = await dispatcher.dispatch(Event(), "foo")

    assert listener.post_foo_invoked
    assert not listener.pre_foo_invoked
    assert factory.calls == 0
    assert dispatcher.get_listener_priority("foo", listener.post_foo) == 0


@pytest.mark.anyio
async def test_a_lazy_listener_is_built_once_an_event_reaches_it(
    dispatcher: EventDispatcher,
) -> None:
    listener = RecordingListener()
    factory = _Factory(listener)
    dispatcher.add_listener("foo", listener.post_foo)
    dispatcher.add_listener("foo", LazyListener(factory, "pre_foo"))
    listener.pre_foo(Event())

    _ = await dispatcher.dispatch(Event(), "foo")

    assert factory.calls == 1


def test_equal_bound_methods_designate_one_listener(dispatcher: EventDispatcher) -> None:
    listener = RecordingListener()
    first = listener.__call__
    second = listener.__call__
    third = RecordingListener().__call__
    assert first is not second

    dispatcher.add_listener("foo", first, 3)
    dispatcher.add_listener("foo", second, 2)
    dispatcher.add_listener("foo", third, 1)

    assert dispatcher.get_listener_priority("foo", first) == 3
    assert dispatcher.get_listener_priority("foo", second) == 3


def test_removing_a_bound_method_removes_every_equal_one(dispatcher: EventDispatcher) -> None:
    listener = RecordingListener()
    third = RecordingListener().__call__
    dispatcher.add_listener("foo", listener.__call__, 3)
    dispatcher.add_listener("foo", listener.__call__, 2)
    dispatcher.add_listener("foo", third, 1)

    dispatcher.remove_listener("foo", listener.__call__)

    assert dispatcher.get_listeners() == {"foo": [third]}


@pytest.mark.anyio
async def test_an_async_listener_is_awaited_before_the_next_one_runs(
    dispatcher: EventDispatcher,
) -> None:
    order: list[str] = []

    async def first() -> None:
        order.append("first")

    dispatcher.add_listener("foo", first, 10)
    dispatcher.add_listener("foo", lambda: order.append("second"))

    _ = await dispatcher.dispatch(Event(), "foo")

    assert order == ["first", "second"]


@pytest.mark.anyio
async def test_a_listener_is_given_only_the_arguments_it_takes(
    dispatcher: EventDispatcher,
) -> None:
    received: list[tuple[object, ...]] = []
    event = Event()

    def event_only(event: object) -> None:
        received.append((event,))

    def with_name(event: object, name: str) -> None:
        received.append((event, name))

    dispatcher.add_listener("foo", event_only)
    dispatcher.add_listener("foo", with_name)

    _ = await dispatcher.dispatch(event, "foo")

    assert received == [(event,), (event, "foo")]


@pytest.mark.anyio
async def test_an_event_class_stands_for_its_name(dispatcher: EventDispatcher) -> None:
    received: list[_OrderPlaced] = []
    dispatcher.add_listener(_OrderPlaced, received.append)

    _ = await dispatcher.dispatch(_OrderPlaced(42), event_name_of(_OrderPlaced))

    assert received == [_OrderPlaced(42)]


@pytest.mark.anyio
async def test_an_event_dispatched_without_a_name_goes_to_its_class(
    dispatcher: EventDispatcher,
) -> None:
    received: list[_OrderPlaced] = []
    dispatcher.add_listener(_OrderPlaced, received.append)

    _ = await dispatcher.dispatch(_OrderPlaced(42))

    assert received == [_OrderPlaced(42)]


def test_a_listener_needing_four_arguments_is_refused(dispatcher: EventDispatcher) -> None:
    def listener(event: object, name: str, dispatcher: object, extra: object) -> None:
        del event, name, dispatcher, extra

    with pytest.raises(ListenerSignatureError):
        dispatcher.add_listener("foo", listener)

    assert not dispatcher.has_listeners("foo")


def test_a_subscriber_naming_a_method_it_lacks_is_refused(dispatcher: EventDispatcher) -> None:
    with pytest.raises(InvalidSubscriberError, match=r"'missing', which it does not have"):
        dispatcher.add_subscriber(_SubscriberWithAMissingMethod())


class _SubscriberWithAMissingMethod(Subscriber):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {PRE_FOO: "missing"}
