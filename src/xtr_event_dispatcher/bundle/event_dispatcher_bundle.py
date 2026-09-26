"""The xtr-event-dispatcher bundle: a dispatcher holding every declared listener.

An application listing :class:`EventDispatcherBundle` gets an event
dispatcher under ``EventDispatcherInterface`` — the contract's, and this
package's — and ``ListenerIntrospectionInterface``. Every listener its scan
finds is on it: classes, methods and functions carrying
``@as_event_listener``, and every :class:`EventSubscriberInterface`.

The dispatcher is a :class:`CompiledEventDispatcher`: its listeners are
fixed when the container is built, each service built only when an event
reaches it, and it refuses to change afterwards — a listener that must live
for one scope goes on a :class:`ScopedEventDispatcher` wrapping it. In debug
mode it is traced, writing to the ``"event"`` logging channel when the
logging bundle is active.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from typing import Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    AutowireDecorated,
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    Target,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_event_dispatcher_contracts import EventDispatcherInterface as DispatcherContract
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface

from xtr_event_dispatcher.compiled_event_dispatcher import CompiledEventDispatcher
from xtr_event_dispatcher.debug.traceable_event_dispatcher import TraceableEventDispatcher
from xtr_event_dispatcher.decorator.event_listener_declaration import (
    EventListenerDeclaration,
    listeners_declared_on,
)
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface
from xtr_event_dispatcher.event_subscriber_interface import EventSubscriberInterface
from xtr_event_dispatcher.exception import InvalidListenerError

from ._declared_listeners import LISTENER_TAG, SUBSCRIBER_TAG, DeclaredListener, declared_listeners
from ._listener_ordering import ordered
from ._listener_reference import ListenerMap
from .event_dispatcher_config import EventDispatcherConfig

__all__ = ["EVENT_CHANNEL", "EventDispatcherBundle"]

EVENT_CHANNEL = "event"
"""The logging channel a traced dispatcher writes to."""


@final
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@as_bundle("event_dispatcher", config=EventDispatcherConfig)
class EventDispatcherBundle(Bundle[EventDispatcherConfig]):
    """Registers the event dispatchers, and every declared listener and subscriber on them."""

    def __init__(self) -> None:
        """Start with no function listener and the default configuration."""
        self._functions: list[tuple[Callable[..., object], EventListenerDeclaration]] = []
        self._config = EventDispatcherConfig()

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """When ``logging`` is active, add the ``event`` channel to its config."""
        if bundle_active(builder, "logging"):
            builder.prepend_extension_config("logging", _add_event_channel)

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register declared listeners and subscribers found by the scan."""
        functions = self._functions

        def register_listener(
            obj: object,
            declaration: EventListenerDeclaration,
            services: ServiceConfigurator,
        ) -> None:
            if isinstance(obj, type):
                # An abstract base only lends its listeners to the classes built from it.
                if not inspect.isabstract(obj):
                    _ = services.set(obj).add_tag(LISTENER_TAG, **_tag_attributes(declaration))
            else:
                functions.append((cast("Callable[..., object]", obj), declaration))

        def register_subscriber(
            obj: object, subscriber: type, services: ServiceConfigurator
        ) -> None:
            del obj
            _ = services.set(subscriber)

        builder.register_attribute_for_autoconfiguration(listeners_declared_on, register_listener)
        builder.register_attribute_for_autoconfiguration(_subscribers_in, register_subscriber)
        _ = builder.register_for_autoconfiguration(EventSubscriberInterface).add_tag(SUBSCRIBER_TAG)

    @override
    def load_extension(
        self,
        config: EventDispatcherConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register a dispatcher per name, traced in debug mode."""
        self._config = config
        trace = (
            config.trace
            if config.trace is not None
            else bool(builder.get_parameter("kernel.debug"))
        )
        traceable = _logged_traceable if bundle_active(builder, "logging") else _traceable
        for name in (None, *config.dispatchers):
            _ = services.set(_dispatcher_factory(name), qualifier=name).set_argument(
                "listeners", {}
            )
            for alias in (DispatcherContract, ListenerIntrospectionInterface):
                services.alias(
                    alias,
                    EventDispatcherInterface,
                    alias_qualifier=name,
                    target_qualifier=name,
                )
            if trace:
                _ = (
                    services.set(traceable, qualifier=name)
                    .set_decorated_service(EventDispatcherInterface, qualifier=name)
                    .add_tag("kernel.reset", method="reset")
                )

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Hand every dispatcher its listeners, in the order they run."""
        names = (None, *self._config.dispatchers)
        by_dispatcher: dict[str | None, dict[str, list[DeclaredListener]]] = {
            name: {} for name in names
        }
        for listener in declared_listeners(builder, self._functions, self._config.aliases()):
            events = by_dispatcher.get(listener.dispatcher)
            if events is None:
                raise InvalidListenerError(
                    listener.label,
                    f"it listens on the dispatcher {listener.dispatcher!r}, which is not "
                    f"configured: add it to EventDispatcherConfig.dispatchers",
                )
            events.setdefault(listener.event_name, []).append(listener)

        for name, events in by_dispatcher.items():
            listeners = ListenerMap(
                {event: ordered(event, group) for event, group in events.items()}
            )
            _ = builder.get_definition(EventDispatcherInterface, name).set_argument(
                "listeners", listeners
            )

    @override
    async def boot(self) -> None:
        """Build every dispatcher, so a function listener the container cannot fill fails here."""
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets this before boot.
            message = "EventDispatcherBundle.boot ran without a container"
            raise RuntimeError(message)

        for name in (None, *self._config.dispatchers):
            _ = await container.get(EventDispatcherInterface, name)


def _dispatcher_factory(name: str | None) -> Callable[..., EventDispatcherInterface]:
    """Build the factory of the dispatcher named ``name``, the default one for ``None``.

    One function per dispatcher, so each carries its own name in the
    container's report.
    """

    def event_dispatcher(
        listeners: ListenerMap, container: ContainerInterface
    ) -> EventDispatcherInterface:
        return CompiledEventDispatcher(
            {
                event: [
                    (reference.listener(container), priority) for priority, reference in references
                ]
                for event, references in listeners.by_event.items()
            },
        )

    if name is not None:
        event_dispatcher.__name__ = f"event_dispatcher_{name}"
        event_dispatcher.__qualname__ = event_dispatcher.__name__

    return event_dispatcher


def _traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
) -> TraceableEventDispatcher:
    """Trace ``dispatcher`` without logging."""
    return TraceableEventDispatcher(dispatcher)


def _logged_traceable(
    dispatcher: Annotated[EventDispatcherInterface, AutowireDecorated()],
    logger: Annotated[LoggerInterface, Target(EVENT_CHANNEL)],
) -> TraceableEventDispatcher:
    """Trace ``dispatcher``, writing to the ``"event"`` channel."""
    return TraceableEventDispatcher(dispatcher, logger)


def _tag_attributes(declaration: EventListenerDeclaration) -> dict[str, object]:
    return {
        "event": declaration.event,
        "method": declaration.method,
        "priority": declaration.priority,
        "dispatcher": declaration.dispatcher,
        "before": declaration.before,
        "after": declaration.after,
    }


def _subscribers_in(obj: object) -> Iterable[type]:
    """Yield ``obj`` when it is a subscriber that declares its events.

    An abstract class, or a base that leaves ``get_subscribed_events`` to its
    subclasses, is not one: it only lends its methods.
    """
    if not isinstance(obj, type) or not issubclass(obj, EventSubscriberInterface):
        return ()
    declares = inspect.getattr_static(obj, "get_subscribed_events") is not _UNDECLARED

    return (obj,) if declares and not inspect.isabstract(obj) else ()


_UNDECLARED = cast("object", vars(EventSubscriberInterface)["get_subscribed_events"])


def _add_event_channel(config: object) -> object:
    """Declare the ``event`` channel through the logging config's own ``with_channels``.

    Duck-typed: this bundle depends on the logging contracts only, never on
    xtr-logging, so it asks the config it is handed rather than importing its
    type.
    """
    with_channels = cast("Callable[[str], object] | None", getattr(config, "with_channels", None))
    return with_channels(EVENT_CHANNEL) if with_channels is not None else config
