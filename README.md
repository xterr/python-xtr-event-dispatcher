<div align="center">

# xtr-event-dispatcher

**Let the parts of an application talk through events: listeners and subscribers run by priority, any of them able to stop the rest.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="core dependencies: 3" src="https://img.shields.io/badge/core%20deps-3-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

When placing an order has to send a receipt, update stock and write an audit line, the code that
places it should not call all three. It dispatches an `OrderPlaced` event; each concern listens
for it on its own, in the order their priorities give, and any listener can stop the ones after
it. Adding a fourth concern is adding a listener, not editing the order code.

- 📣 **Async dispatch** — listeners are plain functions or `async def`, awaited one after another.
- 🔢 **Priorities and stopping** — higher runs first; an event a listener stops goes no further.
- 🧾 **Subscribers** — a class declaring every event it listens to, in one place.
- 💤 **Lazy listeners** — the object a listener belongs to is built when an event first reaches it.
- 🔒 **Immutable, scoped, compiled** — hand a dispatcher out without letting anyone change it,
  and add listeners for one scope without touching a shared one.
- 🧩 **A bundle** — `@as_event_listener` on a class, a method or a function, and the container
  wires it, ordered by priority and `before`/`after`.
- 🔍 **Tracing** — which listeners ran, which did not, and which events nobody heard.

## Install

```sh
uv add xtr-event-dispatcher
```

With a container:

```sh
uv add "xtr-event-dispatcher[di]"
```

A library that only *dispatches* events depends on
[xtr-event-dispatcher-contracts](../xtr-event-dispatcher-contracts) instead, and leaves the
dispatcher to the application.

## Quick start

```python
from dataclasses import dataclass

from xtr_event_dispatcher import Event, EventDispatcher


@dataclass(frozen=True)
class OrderPlaced(Event):
    order_id: int


async def send_receipt(event: OrderPlaced) -> None: ...


def reject_fraud(event: OrderPlaced) -> None:
    if is_fraudulent(event.order_id):
        event.stop_propagation()  # send_receipt will not run


dispatcher = EventDispatcher()
dispatcher.add_listener(OrderPlaced, reject_fraud, priority=100)
dispatcher.add_listener(OrderPlaced, send_receipt)

await dispatcher.dispatch(OrderPlaced(42))
```

## Events and names

An event is any object; derive from `Event` to let listeners stop it. Events are keyed by
**name**: a string, or a class standing for `"<module>.<qualname>"`. `dispatch(event)` without a
name uses the event's class, so `add_listener(OrderPlaced, ...)` and
`dispatch(OrderPlaced(42))` meet. A listener of a base class does not hear its subclasses: a
package wanting a broad audience dispatches one event class per situation.

`GenericEvent` is an event without a class of its own: a subject, and arguments read like a
mapping.

```python
event = await dispatcher.dispatch(GenericEvent(order, {"notify": True}), "order.saved")
if event["notify"]:
    ...
```

## Listeners

A listener is called with up to three arguments — the event, the name it was dispatched under,
and the dispatcher — **as many as it takes**, by position. What it returns is ignored, except
that an awaitable is awaited before the next listener runs. Adding one that requires more
raises `ListenerSignatureError` there and then.

```python
def log(event: OrderPlaced) -> None: ...
def route(event: Event, name: str) -> None: ...
async def chain(event: Event, name: str, dispatcher: EventDispatcherInterface) -> None: ...
```

Listeners run by priority, highest first; sharing a priority, in the order added. Bound methods
of one object compare equal, so `remove_listener(event, obj.method)` removes what
`add_listener(event, obj.method)` added.

### Subscribers

```python
class OrderMailer(EventSubscriberInterface):
    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            OrderPlaced: "on_placed",  # priority 0
            OrderShipped: ("on_shipped", 10),  # (method, priority)
            OrderCancelled: [  # several listeners
                "notify_customer",
                {"method": "notify_warehouse", "priority": -5},
            ],
        }


dispatcher.add_subscriber(OrderMailer())
```

A mapping may also carry `before`/`after` (see below); a dispatcher on its own cannot honour
them, so it requires a `priority` beside them and ignores them — a container orders by them.

### Lazy listeners

```python
dispatcher.add_listener(OrderPlaced, LazyListener(build_mailer, "on_placed"))
```

`build_mailer` is awaited just before the listener first runs — never, when an earlier listener
stops the event — and what it built is kept. Until then `get_listeners` returns the
`LazyListener`; afterwards, the bound method.

## Dispatchers

| Class | What it is for |
|---|---|
| `EventDispatcher` | The one listeners are registered on. |
| `ImmutableEventDispatcher(dispatcher)` | Hand a dispatcher out for dispatching only: every change raises `BadMethodCallError`. |
| `ScopedEventDispatcher(dispatcher)` | Listeners for one scope — a request, a command, a test — next to those of a shared dispatcher, which is left as it is. They interleave by priority. |
| `CompiledEventDispatcher(listeners)` | Listeners fixed when it is built, then refusing every change. What the container builds. |
| `debug.TraceableEventDispatcher(dispatcher, logger=None)` | Records which listeners ran and how often, which did not, and which events nobody heard; `reset()` between units of work. |

A listener receives the dispatcher that ran it: the scoped, compiled or traceable one itself, but
the wrapped one through an `ImmutableEventDispatcher`, which dispatches by delegating.

## Kernel / bundle

```python
# app/bundles.py
from xtr_event_dispatcher.bundle import EventDispatcherBundle

BUNDLES = {EventDispatcherBundle: {"all": True}}
```

The application gets a dispatcher under `EventDispatcherInterface` — the contract's and this
package's — and `ListenerIntrospectionInterface`, holding every listener its scan finds:

```python
from xtr_dependency_injection import Injected
from xtr_event_dispatcher import as_event_listener


@as_event_listener()  # the event is the first parameter's type
async def send_receipt(event: OrderPlaced, mailer: Injected[Mailer]) -> None: ...


class Stock:  # built when an event first reaches it
    def __init__(self, repository: StockRepository) -> None: ...

    @as_event_listener(priority=10)
    def reserve(self, event: OrderPlaced | OrderEdited) -> None: ...


@as_event_listener(OrderShipped)  # calls on_order_shipped, else __call__
class Notifier:
    def on_order_shipped(self, event: OrderShipped) -> None: ...


class Audit(EventSubscriberInterface): ...  # every subscriber is registered
```

`@as_event_listener(event=None, *, method=None, priority=None, dispatcher=None, before=None,
after=None)`, repeatable, on a class, a method — static and class methods included, above or
below their decorator — or a function:

- **`event`** — a name or a class. Without it, the first parameter's annotation — each member
  of a union — is the event; the base `Event` does not count. Annotations must be importable
  at runtime.
- **`method`** — on a class only. Without it, the class is called through `__call__` when the
  event is read from its signature, else `on_<event>` (`on_order_placed` for `OrderPlaced` or
  `"order.placed"`), then `__call__`. On a method it is an error: the method is the one called.
- **`before` / `after`** — classes, functions or methods, or `"module:Qualified.name"`
  strings; a callable object is refused. A listener with a `priority` keeps it and is only
  reordered among its equals; one without takes the priority its place needs. A target naming
  something not installed is ignored; a `Class.method` whose class listens through another
  method is an error. An inherited method is also known by the class defining it.
- **`dispatcher`** — a named dispatcher from `EventDispatcherConfig.dispatchers`, injected with
  `Annotated[EventDispatcherInterface, Target("audit")]`.

A function's own parameters come first; the ones the container fills — `Injected[...]`,
`Autowire(...)`, `Target(...)` — follow. A listener class is a singleton: the dispatcher keeps
it once built.

Listener methods are inherited: every scanned class carrying one listens, its subclasses
included. To keep a base class from listening itself, make it abstract (an `ABC` with an
abstract method) or mark it `@exclude`. A subscriber base that leaves `get_subscribed_events`
to its subclasses is not registered either.

**The container's dispatcher cannot be changed.** It is a `CompiledEventDispatcher` shared for
the process's lifetime, so a listener added at runtime would outlive the request, message or
task that added it; a listener receiving the dispatcher receives that one too. For listeners of
one scope, wrap it: `ScopedEventDispatcher(dispatcher)`.

A bundle tags a service by hand the way the decorator does:

```python
services.set(Stock).add_tag("event_dispatcher.listener", event=OrderPlaced, method="reserve")
services.set(Audit).add_tag("event_dispatcher.subscriber", dispatcher="audit")
```

### Configuration

```python
@configure
def events() -> EventDispatcherConfig:
    return EventDispatcherConfig(
        # a listener of "order.placed" hears OrderPlaced
        event_aliases={"order.placed": OrderPlaced},
        dispatchers=("audit",),  # besides the default one
        trace=None,  # None: trace in debug mode
    )
```

Another bundle adds aliases with `builder.prepend_extension_config("event_dispatcher", ...)`.

In debug mode every dispatcher is wrapped in a `TraceableEventDispatcher`, reset between units of
work (`kernel.reset`); with the logging bundle active it writes to the `"event"` channel.

The bundle's zero-config path builds an empty dispatcher and does no I/O.

## Errors

Every error derives from `EventDispatcherError`. An exception raised by a listener is not
wrapped: it reaches the code that dispatched the event.

| Error | Raised when |
|---|---|
| `ListenerSignatureError` (`TypeError`) | A listener requires more than the event, its name and the dispatcher |
| `InvalidSubscriberError` (`ValueError`) | A subscriber's declaration has no known shape, names a method it lacks, or orders without a priority on a plain dispatcher |
| `InvalidListenerError` (`ValueError`) | While the container is built: no event to read, a missing method, an unknown dispatcher, ordering constraints that cannot be met |
| `BadMethodCallError` (`RuntimeError`) | A change to an immutable or compiled dispatcher |
| `ArgumentNotFoundError` (`KeyError`) | A `GenericEvent` has no such argument |
| `InvalidArgumentError` (`ValueError`) | An `EventDispatcherConfig` cannot be read |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-event-dispatcher`; run the commands below from there. The
`python-xtr-event-dispatcher` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
