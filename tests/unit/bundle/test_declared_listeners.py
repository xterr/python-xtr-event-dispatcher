from __future__ import annotations

# ``typing`` itself, not only names from it: Legacy's string annotation reads it.
import typing
from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from typing import cast, final

import pytest
from typing_extensions import override
from xtr_dependency_injection import (
    Injected,  # noqa: TC002 — read at runtime, from the listeners' annotations.
)

from xtr_event_dispatcher import (
    Event,
    EventSubscriberInterface,
    InvalidListenerError,
    SubscribedEvents,
)
from xtr_event_dispatcher.bundle._declared_listeners import (
    LISTENER_TAG,
    SUBSCRIBER_TAG,
    DeclaredListener,
    declared_listeners,
)
from xtr_event_dispatcher.bundle._listener_reference import FunctionListener, ServiceListener
from xtr_event_dispatcher.decorator import EventListenerDeclaration

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder

_Key = tuple[type, Hashable | None]


class OrderPlaced(Event):
    pass


@dataclass(frozen=True)
class _Definition:
    provider: object
    lifetime: str = "singleton"


@final
@dataclass
class _Builder:
    """What reading listeners asks of a container builder: tagged services and their classes."""

    tags: dict[str, dict[_Key, list[dict[str, object]]]] = field(default_factory=dict)
    lifetimes: dict[type, str] = field(default_factory=dict)

    def find_tagged_service_ids(self, tag: str) -> dict[_Key, list[dict[str, object]]]:
        return self.tags.get(tag, {})

    def find_definition(self, service: type, qualifier: Hashable | None = None) -> _Definition:
        del qualifier
        return _Definition(service, self.lifetimes.get(service, "singleton"))


def _listeners_of(
    tagged: Mapping[type, list[dict[str, object]]] | None = None,
    subscribers: Mapping[type, list[dict[str, object]]] | None = None,
    functions: list[tuple[Callable[..., object], EventListenerDeclaration]] | None = None,
) -> list[DeclaredListener]:
    builder = _Builder(
        {
            LISTENER_TAG: {(cls, None): tags for cls, tags in (tagged or {}).items()},
            SUBSCRIBER_TAG: {(cls, None): tags for cls, tags in (subscribers or {}).items()},
        },
    )
    return declared_listeners(
        cast("ContainerBuilder", cast("object", builder)), functions or [], {}
    )


class Stock:
    def on_order_placed(self, _event: OrderPlaced) -> None: ...

    def __call__(self, _event: OrderPlaced | None) -> None: ...

    def four(self, _a: object, _b: object, _c: object, _d: object) -> None: ...

    @staticmethod
    def static(_event: OrderPlaced) -> None: ...


class Legacy:
    def __call__(self, _event: object) -> None: ...


# The ``Optional[...]`` spelling, which has an origin of its own; written as a
# string so that nothing else here has to use it.
Legacy.__call__.__annotations__ = {"_event": "typing.Optional[OrderPlaced]", "return": "None"}


class Plain:
    pass


class Audit(EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {"order.placed": "record"}

    def record(self) -> None: ...


def test_an_event_named_by_the_tag_picks_the_on_method() -> None:
    [listener] = _listeners_of({Stock: [{"event": OrderPlaced}]})

    assert listener.reference == ServiceListener(Stock, None, "on_order_placed")
    assert listener.names == (f"{__name__}:Stock", f"{__name__}:Stock.on_order_placed")


def test_a_named_event_without_an_on_method_calls_the_object() -> None:
    [listener] = _listeners_of({Stock: [{"event": "order.shipped"}]})

    assert listener.reference == ServiceListener(Stock, None, "__call__")


def test_a_class_declaring_nothing_reads_the_event_from_call_and_calls_it() -> None:
    [listener] = _listeners_of({Stock: [{}]})

    assert listener.event_name == f"{__name__}.OrderPlaced"
    assert listener.reference == ServiceListener(Stock, None, "__call__")


def test_a_static_method_is_read_without_a_bound_first_parameter() -> None:
    [listener] = _listeners_of({Stock: [{"method": "static"}]})

    assert listener.event_name == f"{__name__}.OrderPlaced"


class Warehouse(Stock):
    pass


def test_an_inherited_method_is_also_named_after_the_class_defining_it() -> None:
    [listener] = _listeners_of({Warehouse: [{"event": "foo", "method": "on_order_placed"}]})

    assert listener.names == (
        f"{__name__}:Warehouse",
        f"{__name__}:Stock.on_order_placed",
        f"{__name__}:Warehouse.on_order_placed",
    )


def test_a_listener_service_that_is_not_a_singleton_is_refused() -> None:
    builder = _Builder({LISTENER_TAG: {(Stock, None): [{"event": "foo"}]}})
    builder.lifetimes[Stock] = "transient"

    with pytest.raises(InvalidListenerError, match="must be a singleton"):
        _ = declared_listeners(cast("ContainerBuilder", cast("object", builder)), [], {})


def test_the_optional_spelling_is_read_as_its_event() -> None:
    [listener] = _listeners_of({Legacy: [{}]})

    assert listener.event_name == f"{__name__}.OrderPlaced"


def test_a_class_with_neither_method_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match='neither "on_order_shipped" nor "__call__"'):
        _ = _listeners_of({Plain: [{"event": "order.shipped"}]})


def test_a_class_without_call_to_read_the_event_from_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="no method '__call__' to read its event from"):
        _ = _listeners_of({Plain: [{}]})


def test_a_method_no_dispatcher_can_call_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="cannot be a listener"):
        _ = _listeners_of({Stock: [{"event": "foo", "method": "four"}]})


def test_a_static_method_is_accepted_as_it_is() -> None:
    [listener] = _listeners_of({Stock: [{"event": "foo", "method": "static"}]})

    assert listener.reference == ServiceListener(Stock, None, "static")


@pytest.mark.parametrize(
    ("attributes", "reason"),
    [
        ({"event": "foo", "priorty": 1}, "unknown attributes"),
        ({"event": 5}, "neither a name nor a class"),
        ({"event": "foo", "method": 5}, "which is not a name"),
        ({"event": "foo", "priority": "high"}, "not an integer"),
        ({"event": "foo", "dispatcher": 5}, "which is not a name"),
        ({"event": "foo", "before": [5]}, "neither a class, a function"),
    ],
)
def test_a_hand_written_tag_that_cannot_be_read_is_refused(
    attributes: dict[str, object],
    reason: str,
) -> None:
    with pytest.raises(InvalidListenerError, match=reason):
        _ = _listeners_of({Stock: [attributes]})


def test_a_subscriber_listens_on_every_dispatcher_its_tags_name() -> None:
    listeners = _listeners_of(subscribers={Audit: [{}, {"dispatcher": "audit"}]})

    assert [listener.dispatcher for listener in listeners] == [None, "audit"]


def test_a_subscriber_tag_on_a_class_that_is_no_subscriber_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="does not derive from EventSubscriberInterface"):
        _ = _listeners_of(subscribers={Plain: [{}]})


def test_a_subscriber_tag_naming_no_dispatcher_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="which is not a name"):
        _ = _listeners_of(subscribers={Audit: [{"dispatcher": 5}]})


def _receipt(_event: OrderPlaced, _name: str, _journal: Injected[Plain]) -> None: ...


def _injected_first(_journal: Injected[Plain], _event: OrderPlaced) -> None: ...


def _four(_event: OrderPlaced, _a: object, _b: object, _c: object) -> None: ...


def test_a_function_counts_only_the_arguments_it_takes_itself() -> None:
    [listener] = _listeners_of(functions=[(_receipt, EventListenerDeclaration())])

    assert listener.reference == FunctionListener(_receipt, 2)
    assert listener.event_name == f"{__name__}.OrderPlaced"


def test_a_function_naming_a_method_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="a function has no method"):
        _ = _listeners_of(functions=[(_receipt, EventListenerDeclaration(method="run"))])


def test_container_parameters_before_the_event_are_refused() -> None:
    with pytest.raises(InvalidListenerError, match="must come after the event"):
        _ = _listeners_of(functions=[(_injected_first, EventListenerDeclaration())])


def test_a_function_taking_four_arguments_is_refused() -> None:
    with pytest.raises(InvalidListenerError, match="cannot be a listener"):
        _ = _listeners_of(functions=[(_four, EventListenerDeclaration())])


def test_annotations_that_cannot_be_read_are_refused() -> None:
    def listener(_event: object) -> None: ...

    listener.__annotations__ = {"_event": "Undefined", "return": "None"}

    with pytest.raises(InvalidListenerError, match="cannot be read at runtime"):
        _ = _listeners_of(functions=[(listener, EventListenerDeclaration())])
