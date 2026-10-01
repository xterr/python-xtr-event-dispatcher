"""Writing the listeners ``debug:event-dispatcher`` found, as text, JSON, Markdown or XML."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal, TypeAlias
from xml.etree.ElementTree import (
    Element,
    SubElement,
    indent,
    tostring,
)

from xtr_console import escape

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_console import ConsoleStyle

    from xtr_event_dispatcher.debug.listener_info import ListenerInfo

__all__ = ["Format", "describe"]

Format: TypeAlias = Literal["txt", "json", "md", "xml"]
"""The formats the command writes; ``txt`` is for a person, the others for a tool."""

Described: TypeAlias = "Sequence[tuple[str, Sequence[ListenerInfo]]]"


def describe(io: ConsoleStyle, output_format: Format, events: Described) -> None:
    """Write each event's listeners, in the order they run, in ``output_format``."""
    match output_format:
        case "txt":
            _text(io, events)
        case "json":
            _raw(io, json.dumps(_mapping(events), indent=2))
        case "md":
            _raw(io, _markdown(events))
        case "xml":
            _raw(io, _xml(events))


def _text(io: ConsoleStyle, events: Described) -> None:
    for name, listeners in events:
        io.section(f'"{escape(name)}" event')
        io.table(
            ("Order", "Callable", "Priority"),
            [
                (f"#{order}", escape(info.pretty), str(info.priority))
                for order, info in enumerate(listeners, start=1)
            ],
        )


def _raw(io: ConsoleStyle, text: str) -> None:
    """Write ``text`` as it is: no markup read in it, no line wrapped."""
    io.console.print(text, markup=False, highlight=False, soft_wrap=True)


def _mapping(events: Described) -> dict[str, list[dict[str, object]]]:
    return {
        name: [{"callable": info.pretty, "priority": info.priority} for info in listeners]
        for name, listeners in events
    }


def _markdown(events: Described) -> str:
    sections = [
        "\n".join(
            [
                f"## {name}",
                "",
                "| Order | Callable | Priority |",
                "| --- | --- | --- |",
                *(
                    f"| #{order} | `{info.pretty}` | {info.priority} |"
                    for order, info in enumerate(listeners, start=1)
                ),
            ]
        )
        for name, listeners in events
    ]
    return "\n\n".join(sections)


def _xml(events: Described) -> str:
    root = Element("event-dispatcher")
    for name, listeners in events:
        event = SubElement(root, "event", name=name)
        for info in listeners:
            listener = SubElement(event, "callable", name=info.pretty)
            if info.priority is not None:
                listener.set("priority", str(info.priority))
    indent(root)
    return tostring(root, encoding="unicode")
