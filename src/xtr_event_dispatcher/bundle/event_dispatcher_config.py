"""Configuration for :class:`~xtr_event_dispatcher.bundle.EventDispatcherBundle`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from xtr_event_dispatcher_contracts import event_name_of

from xtr_event_dispatcher.exception import InvalidArgumentError

__all__ = ["EventDispatcherConfig"]


@dataclass(frozen=True, slots=True)
class EventDispatcherConfig:
    """How the bundle builds the container's event dispatchers.

    Buildable with no arguments: an application listing the bundle without
    configuring it gets one dispatcher holding every listener its scan finds.

    ```python
    EventDispatcherConfig(
        event_aliases={"order.placed": OrderPlaced},
        dispatchers=("audit",),
    )
    ```

    Attributes:
        event_aliases: Event names — or classes — that listeners declare,
            mapped to the event they really listen to. Lets a library offer
            a short name for one of its events, and lets another bundle add
            its own with ``prepend_extension_config``.
        dispatchers: Dispatchers besides the default one, each registered
            under its name as the qualifier. A listener joins one with
            ``@as_event_listener(dispatcher="audit")``.
        trace: Wrap every dispatcher in a
            :class:`~xtr_event_dispatcher.debug.TraceableEventDispatcher`.
            ``None`` traces when the kernel is in debug mode.
    """

    event_aliases: Mapping[str | type, str | type] = field(
        default_factory=dict[str | type, str | type],
    )
    dispatchers: tuple[str, ...] = ()
    trace: bool | None = None

    def __post_init__(self) -> None:
        """Refuse a dispatcher name that is empty or given twice, and an alias that is not a name.

        Raises:
            InvalidArgumentError: When the configuration cannot be read.
        """
        for name in self.dispatchers:
            if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
                raise InvalidArgumentError(f"a dispatcher needs a non-empty name, got {name!r}")
        if len(set(self.dispatchers)) != len(self.dispatchers):
            raise InvalidArgumentError(f"a dispatcher is named twice in {self.dispatchers!r}")
        for alias, event in self.event_aliases.items():
            if not isinstance(alias, str | type) or not isinstance(event, str | type):  # pyright: ignore[reportUnnecessaryIsInstance] -- as above
                raise InvalidArgumentError(
                    f"an event alias maps a name or a class to one, got {alias!r}: {event!r}",
                )

    def aliases(self) -> dict[str, str]:
        """Return the event aliases with every class replaced by its event name."""
        aliases = self.event_aliases.items()
        return {event_name_of(alias): event_name_of(event) for alias, event in aliases}
