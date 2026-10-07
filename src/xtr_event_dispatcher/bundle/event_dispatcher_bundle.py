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

The dispatcher's factory is the one service here given the container
itself, and on purpose: what it holds is known only once every bundle has
registered, and is heterogeneous — services of any type and qualifier,
fetched lazily the first time an event reaches them, and listener functions
whose own container-supplied parameters are resolved on every call. A
``ServiceLocator[T]`` is keyed by name over one type and cannot resolve a
function's parameters, so it cannot stand in for either.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from typing import cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    BUNDLE_PASS_PRIORITY,
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    required_bundle,
)

from xtr_event_dispatcher.decorator.event_listener_declaration import (
    EventListenerDeclaration,
    listeners_declared_on,
)
from xtr_event_dispatcher.event_dispatcher_interface import EventDispatcherInterface
from xtr_event_dispatcher.event_subscriber_interface import EventSubscriberInterface

from ._declared_listeners import DISPATCHER_TAG, LISTENER_TAG, SUBSCRIBER_TAG
from .event_dispatcher_config import EventDispatcherConfig
from .event_dispatcher_factory import (
    EVENT_CHANNEL,
    event_dispatcher_factory,
    traceable_event_dispatcher_factory,
)
from .register_listeners_pass import RegisterListenersPass

__all__ = ["EventDispatcherBundle"]


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
        """Register the listeners and subscribers the scan finds, and the pass handing them over.

        The pass runs after every bundle's ``process`` hook, so a listener a
        bundle tags there joins its dispatcher too.
        """
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
        builder.add_compiler_pass(
            RegisterListenersPass(functions),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=BUNDLE_PASS_PRIORITY,
        )

    @override
    def load_extension(
        self,
        config: EventDispatcherConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register a dispatcher per name, traced in debug mode, and the console command.

        The command joins in debug mode only, when a console bundle is active.
        """
        self._config = config
        debug = bool(builder.get_parameter("kernel.debug"))
        trace = config.trace if config.trace is not None else debug
        traceable = traceable_event_dispatcher_factory(logged=bundle_active(builder, "logging"))
        for name in (None, *config.dispatchers):
            _ = services.set(event_dispatcher_factory(name), qualifier=name).add_tag(DISPATCHER_TAG)
            if trace:
                _ = (
                    services.set(traceable, qualifier=name)
                    .set_decorated_service(EventDispatcherInterface, qualifier=name)
                    .add_tag("kernel.reset", method="reset")
                )
        if debug and bundle_active(builder, "console"):
            services.load("xtr_event_dispatcher.command")

    @override
    async def boot(self) -> None:
        """Build every dispatcher, so a function listener the container cannot fill fails here."""
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets this before boot.
            message = "EventDispatcherBundle.boot ran without a container"
            raise RuntimeError(message)

        for name in (None, *self._config.dispatchers):
            _ = await container.get(EventDispatcherInterface, name)


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
