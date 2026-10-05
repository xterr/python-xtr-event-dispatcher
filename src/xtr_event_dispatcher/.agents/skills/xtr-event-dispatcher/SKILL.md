---
name: xtr-event-dispatcher
description: How to emit events and register listeners with xtr-event-dispatcher and xtr-event-dispatcher-contracts. Use when one part of an application must react to another without being called by it — order placed, message consumed, request handled — or when you see dispatch(), add_listener, add_subscriber, @as_event_listener, EventSubscriberInterface, GenericEvent, LazyListener, priorities, stop_propagation, before/after ordering, named dispatchers, a listener that must not fire, or EventDispatcherBundle being added to an application on xtr-dependency-injection; also when a library should announce something happened without choosing who hears it.
---

# xtr-event-dispatcher

Code that announces something dispatches an event; the listeners registered for that event's
name run from the highest priority down, and any of them can stop the rest. Adding a concern is
adding a listener, never editing the code that dispatched.

## Quick reference

- Define an event: a frozen dataclass deriving from `Event`. Deriving from `Event` is what lets
  a listener call `event.stop_propagation()`.
- Dispatch: `event = await dispatcher.dispatch(OrderPlaced(42))`. The same object comes back,
  so listeners that mutate it are read afterwards.
- Register by hand: `dispatcher.add_listener(OrderPlaced, send_receipt, priority=100)`.
- Register from a container: `@as_event_listener()` on a function, a method or a class.
- A class holding several listeners: implement `EventSubscriberInterface`, then
  `dispatcher.add_subscriber(instance)`.
- A library that only dispatches depends on `xtr-event-dispatcher-contracts` and types against
  `xtr_event_dispatcher_contracts.EventDispatcherInterface`.
- In an application: activate `EventDispatcherBundle`, inject `EventDispatcherInterface`.
- Never add a listener to the container's dispatcher at runtime; wrap it in
  `ScopedEventDispatcher`.

## Events

```python
from dataclasses import dataclass

from xtr_event_dispatcher import Event


@dataclass(frozen=True)
class OrderPlaced(Event):
    order_id: int
```

- Events are keyed by **name**: a string, or a class standing for `"<module>.<qualname>"`
  (`event_name_of(OrderPlaced)`). `dispatch(event)` with no name uses the event's class, so
  `add_listener(OrderPlaced, ...)` and `dispatch(OrderPlaced(42))` meet.
- **A listener of a base class does not hear its subclasses.** Dispatch one event class per
  situation instead of relying on inheritance.
- An event need not derive from `Event`; any object works, but then nothing can stop it.
- `GenericEvent` is an event with no class of its own — a subject plus arguments read like a
  mapping. Besides `event["key"]` it answers `get_subject()`, `get_argument`, `set_argument`,
  `get_arguments`, `set_arguments`, `has_argument`, `in`, `len()` and iteration over its keys.

```python
from xtr_event_dispatcher import GenericEvent

event = await dispatcher.dispatch(GenericEvent(order, {"notify": True}), "order.saved")
if event["notify"]:
    ...
```

## Listeners

A listener is called with up to three arguments — the event, the name it was dispatched under,
and the dispatcher — **as many as it takes**, by position. Take only what you use:

```python
def log(event: OrderPlaced) -> None: ...
def route(event: Event, name: str) -> None: ...
async def chain(event: Event, name: str, dispatcher: EventDispatcherInterface) -> None: ...
```

- Plain functions and `async def` both work; an awaitable result is awaited before the next
  listener runs. Anything else returned is ignored.
- A listener requiring a fourth argument raises `ListenerSignatureError` at `add_listener`.
- Order: highest priority first; listeners sharing a priority run in the order added.
- Bound methods of one object compare equal, so `remove_listener(event, obj.method)` removes
  what `add_listener(event, obj.method)` added.
- A listener added during a dispatch first runs on the next one; one removed during a dispatch
  does not run for the rest of it.

### Stopping the rest

```python
def reject_fraud(event: OrderPlaced) -> None:
    if is_fraudulent(event.order_id):
        event.stop_propagation()  # lower-priority listeners never run


dispatcher.add_listener(OrderPlaced, reject_fraud, priority=100)
dispatcher.add_listener(OrderPlaced, send_receipt)  # priority 0
```

Read it back with `event.is_propagation_stopped()`. Stopping only works on an event deriving
from `Event` (or implementing `StoppableEventInterface`).

### Subscribers

```python
from collections.abc import Mapping
from typing import override

from xtr_event_dispatcher import EventSubscriberInterface, SubscribedEvents


class OrderMailer(EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            OrderPlaced: "on_placed",  # priority 0
            OrderShipped: ("on_shipped", 10),  # (method, priority)
            OrderCancelled: [  # several listeners for one event
                "notify_customer",
                {"method": "notify_warehouse", "priority": -5},
            ],
        }

    def on_placed(self, event: OrderPlaced) -> None: ...


dispatcher.add_subscriber(OrderMailer())
```

`get_subscribed_events` is a classmethod read before any instance exists: it must not depend on
state. A declaration dict is a `SubscribedListener` and may carry `before`/`after`
(`OrderTarget`), but a plain dispatcher cannot honour them — it requires a `priority` beside
them and ignores them; only a container orders by them.

### Lazy listeners

```python
from xtr_event_dispatcher import LazyListener

dispatcher.add_listener(OrderPlaced, LazyListener(build_mailer, "on_placed"))
```

`build_mailer` is an `async` callable taking no arguments, awaited just before the listener first runs — never, if an earlier listener
stopped the event — and what it built is kept. Omit the method name to call the object itself.

## Dispatchers

| Class | Use for |
| --- | --- |
| `EventDispatcher()` | The one you register listeners on. |
| `ImmutableEventDispatcher(inner)` | Handing a dispatcher out for dispatching only; every change raises `BadMethodCallError`. |
| `ScopedEventDispatcher(inner)` | Listeners for one scope — a request, a command, a test — beside a shared dispatcher's, which is left untouched. They interleave by priority. |
| `CompiledEventDispatcher({OrderPlaced: [(send_receipt, 10)]})` | Listeners fixed at construction, then refusing every change. What the container builds. |
| `xtr_event_dispatcher.debug.TraceableEventDispatcher(inner, logger=None)` | Seeing what ran. |

Read listeners without registering any: `get_listeners(name)` in running order (or every
event's, with no argument), `get_listener_priority(name, listener)`, `has_listeners(name=None)`.
A listener receives the dispatcher that ran it — the scoped, compiled or traceable one itself,
but the *wrapped* one through an `ImmutableEventDispatcher`.

`TraceableEventDispatcher` answers `get_called_listeners()`, `get_not_called_listeners()` (both
lists of `ListenerInfo`: `.event`, `.priority`, `.pretty`, `.calls`, `.duration` in seconds) and
`get_orphaned_events()`; `reset()` clears it, and `begin_unit()` / `end_unit()` keep
overlapping units of work out of each other's trace.

## A library that only dispatches

Depend on `xtr-event-dispatcher-contracts` alone — not on the implementation — and let the
application pick the dispatcher. `xtr-event-dispatcher` re-exports `Event`,
`StoppableEventInterface`, `ListenerIntrospectionInterface`, `Listener` and `event_name_of`
rather than redefining them, so both sides name the same objects. Full example in
[references/contracts.md](references/contracts.md).

| Type against | When |
| --- | --- |
| `xtr_event_dispatcher_contracts.EventDispatcherInterface` | You only `dispatch`. |
| `xtr_event_dispatcher_contracts.ListenerIntrospectionInterface` | You only read listeners. |
| `xtr_event_dispatcher.IntrospectableDispatcherInterface` | You dispatch and read listeners, never register — what `ImmutableEventDispatcher` and `ScopedEventDispatcher` wrap. |
| `xtr_event_dispatcher.EventDispatcherInterface` | You also register listeners — it extends both of the above. |

## Testing

There is no fake to install: a real `EventDispatcher` **is** the test double.

```python
from xtr_event_dispatcher import EventDispatcher


@pytest.mark.anyio
async def test_the_worker_announces_what_it_consumed() -> None:
    heard: list[MessageConsumed] = []
    dispatcher = EventDispatcher()
    dispatcher.add_listener(MessageConsumed, heard.append)

    await Worker(dispatcher).handled("m-1")

    assert heard == [MessageConsumed("m-1")]
```

- Asserting a listener did *not* run: dispatch, then check your recorder is empty — or wrap in
  `TraceableEventDispatcher` and read `get_not_called_listeners()`.
- A kernel test replaces the service:
  `boot_for_test(kernel, overrides={EventDispatcherInterface: EventDispatcher()})`.
- Adding a listener for one test around a booted application:
  `ScopedEventDispatcher(container_dispatcher)`.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`EventDispatcherBundle`, or leaves it out when the messenger or scheduler bundle already requires
it. That is the steps below a recipe can do; the others it prints for you to make.

1. **Install** — `uv add "xtr-event-dispatcher[di]"`; add the `console` extra for
   `debug:event-dispatcher` in debug mode.
2. **Activate** — `EventDispatcherBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`
   (`from xtr_event_dispatcher.bundle import EventDispatcherBundle`). Nothing to do when the
   messenger or scheduler bundle is listed: both require it when it is installed.
3. **Brings along** — the logging bundle, when xtr-logging is installed.
4. **Configure** — optional. With no configuration there is one empty dispatcher and every
   scanned listener joins it:

   ```python
   # <app>/config/event_dispatcher.py
   from xtr_dependency_injection import configure
   from xtr_event_dispatcher.bundle import EventDispatcherConfig


   @configure
   def event_dispatcher() -> EventDispatcherConfig:
       return EventDispatcherConfig(
           event_aliases={"order.placed": OrderPlaced},  # a listener of the name hears the class
           dispatchers=("audit",),  # besides the default one
           trace=None,  # None: trace in debug mode
       )
   ```

5. **Environment** — nothing.
6. **Use** — inject `EventDispatcherInterface` (the contract's name and this package's both
   resolve to it), or `ListenerIntrospectionInterface` to read what the scan found. Declare
   listeners where they are written:

   ```python
   from xtr_dependency_injection import Injected
   from xtr_event_dispatcher import as_event_listener


   @as_event_listener()  # the event is the first parameter's annotation
   async def send_receipt(event: OrderPlaced, mailer: Injected[Mailer]) -> None: ...


   class Stock:  # built when an event first reaches it
       @as_event_listener(priority=10)
       def reserve(self, event: OrderPlaced | OrderEdited) -> None: ...
   ```

   `@as_event_listener(event=None, *, method=None, priority=None, dispatcher=None, before=None,
   after=None)` is repeatable, and goes on a class, a method (static and class methods included)
   or a function. Every class implementing `EventSubscriberInterface` is registered too. See
   [references/bundle.md](references/bundle.md) for every argument, ordering with
   `before`/`after`, named dispatchers, tagging a service by hand, and which classes the scan
   picks up.
7. **Check** — `debug:bundles` shows `event_dispatcher` as `listed` or `required`, and `active`;
   in debug mode, `debug:event-dispatcher` lists every listener, in running order.
8. **Remove** — drop the `BUNDLES` entry and every `@as_event_listener`, delete
   `<app>/config/event_dispatcher.py`, then `uv remove xtr-event-dispatcher`.

## Errors

Every error derives from `EventDispatcherError`. **An exception a listener raises is not
wrapped**: it reaches whoever dispatched the event, and the listeners after it do not run.

| Error | Raised when |
| --- | --- |
| `ListenerSignatureError` (`TypeError`) | `add_listener` is given something needing more than the event, its name and the dispatcher |
| `InvalidSubscriberError` (`ValueError`) | A subscriber's declaration has no known shape, names a method it lacks, or orders without a priority on a plain dispatcher |
| `InvalidListenerError` (`ValueError`) | While the container is built: no event to read, a missing method, an unknown dispatcher, ordering that cannot be satisfied |
| `BadMethodCallError` (`RuntimeError`) | A change to an immutable or compiled dispatcher |
| `ArgumentNotFoundError` (`KeyError`) | A `GenericEvent` has no such argument |
| `InvalidArgumentError` (`ValueError`) | An `EventDispatcherConfig` cannot be read |

## Do not

- Do not `add_listener` on the dispatcher a container gave you — it is a shared
  `CompiledEventDispatcher` and raises `BadMethodCallError`. Wrap it in `ScopedEventDispatcher`.
- Do not expect a listener of a base event class to hear a subclass of it.
- Do not give a listener a parameter the dispatcher cannot fill; only container-filled ones
  (`Injected[...]`, `Autowire(...)`, `Target(...)`) may follow the first three, and only
  through the bundle.
- Do not rely on `before`/`after` on a plain `EventDispatcher`; it ignores them and demands a
  `priority`.
- Do not call `stop_propagation()` on an event that does not derive from `Event`.
- Do not read a result out of a listener: return values are discarded. Mutate the event, or use
  `GenericEvent` arguments.
- Do not build state in `get_subscribed_events`; it is a classmethod read before any instance
  exists.
