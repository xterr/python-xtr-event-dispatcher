# Emitting events from a library

A library that announces what happened should not decide who hears it. Depend on
`xtr-event-dispatcher-contracts` — no dependencies of its own — take an
`EventDispatcherInterface`, and leave the listeners to the application.

```sh
uv add xtr-event-dispatcher-contracts
```

```python
from __future__ import annotations

from dataclasses import dataclass

from xtr_event_dispatcher_contracts import Event, EventDispatcherInterface


@dataclass(frozen=True)
class MessageConsumed(Event):
    message_id: str


class Worker:
    def __init__(self, events: EventDispatcherInterface) -> None:
        self._events = events

    async def handled(self, message_id: str) -> None:
        await self._events.dispatch(MessageConsumed(message_id))
```

## What the contract holds

| Symbol | What it is |
| --- | --- |
| `EventDispatcherInterface` | `async def dispatch(self, event: T, event_name: str \| type \| None = None) -> T` — the only method, and the event comes back. |
| `Event` | The base class a listener can stop: `stop_propagation()`, `is_propagation_stopped()`. Works as a frozen dataclass base. |
| `StoppableEventInterface` | The protocol `Event` satisfies, for an event with another base. |
| `ListenerIntrospectionInterface` | `get_listeners(name=None)` in running order, `get_listener_priority(name, listener)`, `has_listeners(name=None)`. |
| `Listener` | `Callable[..., object]` — what a dispatcher calls. |
| `event_name_of(event_or_class)` | The name an event is keyed by: `"<module>.<qualname>"`. |

Both packages' symbols are the same objects, so a library written against the contracts and an
application running `xtr-event-dispatcher` never hold two different `Event` classes.

## Rules the contract guarantees

- **Names.** Without an `event_name`, an event is dispatched under its class's name.
- **Order.** Listeners run highest priority first, one after another, each awaited before the
  next.
- **Errors.** An exception a listener raises reaches the caller unchanged.
- **Stopping.** A `StoppableEventInterface` reaches no further listeners once one stops it.
- **Arguments.** A listener is called with the event, its name and the dispatcher — as many of
  the three as it takes, by position; an awaitable result is awaited.

## Which interface to take

| Take | When |
| --- | --- |
| `xtr_event_dispatcher_contracts.EventDispatcherInterface` | You only dispatch. This is almost always the right one for a library. |
| `xtr_event_dispatcher_contracts.ListenerIntrospectionInterface` | You only read listeners. |
| `xtr_event_dispatcher.EventDispatcherInterface` | You also register listeners; it extends both of the above with `add_listener`, `add_subscriber`, `remove_listener`, `remove_subscriber`. |

Do not make the dispatcher optional with a `None` default and guard every call site. Require it,
and let the application hand over a plain `EventDispatcher` with no listeners when nobody cares
yet.

## Testing a library that dispatches

Install `xtr-event-dispatcher` as a dev dependency and use a real `EventDispatcher`: register a
recording listener, call the code, assert on what it heard.
