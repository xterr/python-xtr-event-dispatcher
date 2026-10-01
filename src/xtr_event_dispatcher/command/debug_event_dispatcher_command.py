"""``debug:event-dispatcher``: the listeners of every event, in the order they run."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape

# The console reads the command's signature at runtime to inject the dispatchers.
from xtr_dependency_injection import ServiceLocator  # noqa: TC002
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface  # noqa: TC002

from xtr_event_dispatcher._prioritized_listeners import prioritized_listeners
from xtr_event_dispatcher.debug.wrapped_listener import WrappedListener

from ._describe import Format, describe

if TYPE_CHECKING:
    from xtr_event_dispatcher.debug.listener_info import ListenerInfo

__all__ = ["DebugEventDispatcherCommand"]


@as_command("debug:event-dispatcher")
@final
class DebugEventDispatcherCommand:
    """Lists the listeners of every event, or of the events matching a name, as they run."""

    __slots__ = ()

    async def __call__(
        self,
        io: ConsoleStyle,
        dispatchers: ServiceLocator[ListenerIntrospectionInterface],
        event: str | None = None,
        *,
        dispatcher: str | None = None,
        output_format: Annotated[Format, Option(name="--format")] = "txt",
    ) -> int:
        """List the listeners event by event, highest priority first.

        Args:
            io: Where the command writes.
            dispatchers: The container's dispatchers, by name; the default
                one under ``None``.
            event: An event name — or part of one, matching every event
                whose name contains it. Every event when left out.
            dispatcher: A named dispatcher to read, rather than the default
                one.
            output_format: ``txt`` for a person; ``json``, ``md`` or ``xml``
                for a tool.
        """
        if dispatcher not in dispatchers:
            known = ", ".join(sorted(str(name) for name in dispatchers.provided_services() if name))
            io.error(
                f'No dispatcher named "{escape(str(dispatcher))}"; the named ones are: '
                f"{escape(known) or 'none'}."
            )
            return ExitCode.INVALID

        read = await dispatchers.get(dispatcher)
        names = _matching(sorted(read.get_listeners()), event)
        if not names and output_format == "txt":
            io.warning(
                "No listener is registered."
                if event is None
                else f'No event matching "{escape(event)}" has a listener.'
            )
            return ExitCode.SUCCESS

        describe(io, output_format, [(name, _described(read, name)) for name in names])
        return ExitCode.SUCCESS


def _matching(names: list[str], event: str | None) -> list[str]:
    """Return the event named ``event``, else every event whose name contains it, any case."""
    if event is None:
        return names
    if event in names:
        return [event]
    needle = event.lower()
    return [name for name in names if needle in name.lower()]


def _described(dispatcher: ListenerIntrospectionInterface, name: str) -> list[ListenerInfo]:
    """Describe the event's listeners as a trace would, each with the priority it runs at."""
    return [
        WrappedListener(listener, priority=priority).get_info(name)
        for priority, listener in prioritized_listeners(dispatcher, name)
    ]
