"""Let the parts of an application talk through events.

Code dispatches an event object; the listeners registered for its name run
from the highest priority down, and any of them can stop the rest. A
subscriber declares every event it listens to in one place.

```python
dispatcher = EventDispatcher()
dispatcher.add_listener(OrderPlaced, send_receipt, priority=10)
dispatcher.add_subscriber(AuditSubscriber())

await dispatcher.dispatch(OrderPlaced(42))
```

- :class:`EventDispatcher` — the dispatcher listeners are registered on.
- :class:`CompiledEventDispatcher` — one whose listeners are fixed up front,
  as a container builds it.
- :class:`ImmutableEventDispatcher` — one handed out for dispatching only.
- :class:`ScopedEventDispatcher` — listeners for one scope, added next to
  those of a shared dispatcher without changing it.
- :class:`LazyListener` — a listener whose object is built when first needed.
- :class:`GenericEvent` — an event with a subject and named arguments.
- :func:`as_event_listener` — declare a listener where it is written, for
  the bundle in :mod:`xtr_event_dispatcher.bundle` to register.
- :mod:`xtr_event_dispatcher.debug` — a dispatcher recording what ran.

The contract — :class:`Event`, :class:`StoppableEventInterface`,
:class:`ListenerIntrospectionInterface`, :data:`Listener`,
:func:`event_name_of` — is re-exported from
``xtr-event-dispatcher-contracts``, so both packages name the same objects.
Its narrower ``EventDispatcherInterface``, for code that only dispatches, is
imported from there; the one here adds registering listeners.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from xtr_event_dispatcher_contracts import (
    Event,
    Listener,
    ListenerIntrospectionInterface,
    StoppableEventInterface,
    event_name_of,
)

from .compiled_event_dispatcher import CompiledEventDispatcher
from .decorator import as_event_listener
from .event_dispatcher import EventDispatcher
from .event_dispatcher_interface import EventDispatcherInterface
from .event_subscriber_interface import EventSubscriberInterface, SubscribedEvents
from .exception import (
    ArgumentNotFoundError,
    BadMethodCallError,
    EventDispatcherError,
    InvalidArgumentError,
    InvalidListenerError,
    InvalidSubscriberError,
    ListenerSignatureError,
)
from .generic_event import GenericEvent
from .immutable_event_dispatcher import ImmutableEventDispatcher
from .lazy_listener import LazyListener
from .scoped_event_dispatcher import ScopedEventDispatcher
from .subscribed_listener import OrderTarget, SubscribedListener

try:
    __version__ = version("xtr-event-dispatcher")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "ArgumentNotFoundError",
    "BadMethodCallError",
    "CompiledEventDispatcher",
    "Event",
    "EventDispatcher",
    "EventDispatcherError",
    "EventDispatcherInterface",
    "EventSubscriberInterface",
    "GenericEvent",
    "ImmutableEventDispatcher",
    "InvalidArgumentError",
    "InvalidListenerError",
    "InvalidSubscriberError",
    "LazyListener",
    "Listener",
    "ListenerIntrospectionInterface",
    "ListenerSignatureError",
    "OrderTarget",
    "ScopedEventDispatcher",
    "StoppableEventInterface",
    "SubscribedEvents",
    "SubscribedListener",
    "__version__",
    "as_event_listener",
    "event_name_of",
]
