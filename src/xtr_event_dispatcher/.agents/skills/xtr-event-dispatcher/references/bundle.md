# Declaring listeners for the container

What `EventDispatcherBundle` reads, and how it orders what it finds. Everything here needs
`uv add "xtr-event-dispatcher[di]"` and the bundle listed in `BUNDLES`.

## `@as_event_listener`

```python
@as_event_listener(
    event=None,
    *,
    method=None,
    priority=None,
    dispatcher=None,
    before=None,
    after=None,
)
```

Repeatable — stack it to listen to several events. Goes on a function, a method, or a class.
On a `staticmethod` or `classmethod` it works above or below that decorator.

| Argument | Meaning |
| --- | --- |
| `event` | The event, as a name or a class. Without it, the first parameter's annotation is the event — every member of a union counts, and the base `Event` does not. Annotations must be importable at runtime. |
| `method` | On a class only: the method to call. An error on a method, which is already the one called. |
| `priority` | Higher runs earlier. Without it, `before`/`after` decide, defaulting to `0`. |
| `dispatcher` | A named dispatcher from `EventDispatcherConfig.dispatchers`, rather than the default one. |
| `before` / `after` | Listeners this one runs before or after. |

### How a class is called

Without `method`:

1. `__call__`, when the event was read from that signature;
2. otherwise `on_<event>` — `on_order_placed` for `OrderPlaced` **or** for `"order.placed"`;
3. otherwise `__call__`.

```python
@as_event_listener(OrderShipped)  # calls on_order_shipped, else __call__
class Notifier:
    def on_order_shipped(self, event: OrderShipped) -> None: ...


@as_event_listener(OrderShipped, method="notify")
class Other:
    def notify(self, event: OrderShipped) -> None: ...
```

A listener class is a singleton built when an event first reaches it, and kept afterwards. Its
constructor is autowired like any other service.

### Parameters the container fills

A function's own parameters come first; the container-filled ones follow.

```python
@as_event_listener()
async def send_receipt(event: OrderPlaced, mailer: Injected[Mailer]) -> None: ...
```

`Injected[...]`, `Autowire(...)` and `Target(...)` are all accepted there.

## Ordering with `before` / `after`

A target is a class (naming every listener it provides), a function, a method, or a
`"module:Qualified.name"` string — the `OrderTarget` alias. A callable object is refused: it has
no name of its own to match.

```python
@as_event_listener(after=Stock, before="app.audit:Audit.record")
def send_receipt(event: OrderPlaced) -> None: ...
```

- A listener **with** a `priority` keeps it, and is only reordered among listeners of the same
  priority.
- One **without** takes whatever priority its place needs.
- A target naming something that is not installed is ignored, so an optional peer costs
  nothing.
- A `Class.method` whose class listens through a *different* method is an error
  (`InvalidListenerError`).
- An inherited method is also known by the class that defines it.
- Constraints that cannot all hold raise `InvalidListenerError` while the container is built,
  not at runtime.

A string target is the way to order against a package you do not import.

## Which classes the scan picks up

- Every class carrying a `@as_event_listener` method listens — **including its subclasses**,
  since the method is inherited.
- To keep a base class from listening itself, make it abstract (an `ABC` with an abstract
  method) or mark it `@exclude` (`from xtr_dependency_injection import exclude`).
- Every class implementing `EventSubscriberInterface` is registered as a subscriber. A
  subscriber base that leaves `get_subscribed_events` to its subclasses is not.

## Named dispatchers

```python
@configure
def event_dispatcher() -> EventDispatcherConfig:
    return EventDispatcherConfig(dispatchers=("audit",))


@as_event_listener(dispatcher="audit")
def record(event: OrderPlaced) -> None: ...
```

Inject one with its qualifier:

```python
from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import EventDispatcherInterface

Audit = Annotated[EventDispatcherInterface, Target("audit")]
```

Naming a dispatcher that is not in `dispatchers` raises `InvalidListenerError` at build time.

## Tagging a service by hand

A bundle registering a listener without the decorator uses the same tags:

```python
services.set(Stock).add_tag("event_dispatcher.listener", event=OrderPlaced, method="reserve")
services.set(Audit).add_tag("event_dispatcher.subscriber", dispatcher="audit")
```

The tag attributes are the decorator's arguments.

## Event aliases

`EventDispatcherConfig.event_aliases` maps a name or class a listener declares to the event it
really listens to, so a library can offer a short name for one of its events:

```python
EventDispatcherConfig(event_aliases={"order.placed": OrderPlaced})
```

Another bundle contributes aliases from its own `prepend_extension` hook:

```python
builder.prepend_extension_config("event_dispatcher", {"event_aliases": {...}})
```

## Tracing in debug mode

`EventDispatcherConfig.trace` is `None` by default, which traces when `kernel.debug` is on.
Then every dispatcher is decorated with a `TraceableEventDispatcher`, reset between units of
work through the `kernel.reset` tag; with the logging bundle active it writes to the `"event"`
channel (`EVENT_CHANNEL` in `xtr_event_dispatcher.bundle`). Set `trace=False` to turn it off in
debug, `trace=True` to keep it in production.

## The container's dispatcher cannot be changed

It is a `CompiledEventDispatcher` shared for the process's lifetime: a listener added at runtime
would outlive the request, message or task that added it, so every change raises
`BadMethodCallError`. A listener receiving the dispatcher receives that same shared one. For
listeners of one scope, wrap it:

```python
scoped = ScopedEventDispatcher(dispatcher)
scoped.add_listener(OrderPlaced, just_for_this_request)
await scoped.dispatch(OrderPlaced(42))  # the shared dispatcher's listeners run too
```
