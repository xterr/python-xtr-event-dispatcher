"""``debug:event-dispatcher`` lists the listeners of a booted application, in debug mode only."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from xml.etree.ElementTree import fromstring

import pytest
from xtr_console import Application, CommandTester
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel

from tests.fixtures.qualified_audit import QualifiedAuditBundle
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_event_dispatcher.command import DebugEventDispatcherCommand

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

_PLACED = "tests.fixtures.app_events.events.OrderPlaced"
_SHIPPED = "tests.fixtures.app_events.events.OrderShipped"


def _kernel(*, debug: bool) -> Kernel:
    return Kernel(
        "tests.fixtures.app_events",
        env="test",
        debug=debug,
        bundles={
            EventDispatcherBundle: {"all": True},
            QualifiedAuditBundle: {"all": True},
            ConsoleBundle: {"all": True},
        },
    )


@pytest.fixture
async def tester() -> AsyncIterator[CommandTester]:
    """Boot the fixture application in debug mode and hand over the command."""
    async with await _kernel(debug=True).boot() as booted:
        yield CommandTester(await booted.container.get(Application), "debug:event-dispatcher")


async def test_it_lists_every_event_with_its_listeners_in_running_order(
    tester: CommandTester,
) -> None:
    exit_code = await tester.execute()

    assert exit_code == 0
    display = tester.display
    assert _PLACED in display
    assert _SHIPPED in display
    assert display.index("Stock") < display.index("Mailer")


async def test_it_lists_the_one_event_named(tester: CommandTester) -> None:
    exit_code = await tester.execute([_SHIPPED])

    assert exit_code == 0
    assert "Shipping" in tester.display
    assert "Mailer" not in tester.display


async def test_part_of_a_name_finds_every_event_containing_it(tester: CommandTester) -> None:
    exit_code = await tester.execute(["ordershipped"])

    assert exit_code == 0
    assert _SHIPPED in tester.display
    assert _PLACED not in tester.display


async def test_an_event_nobody_listens_to_is_reported(tester: CommandTester) -> None:
    exit_code = await tester.execute(["nothing.listens"])

    assert exit_code == 0
    assert "nothing.listens" in tester.display + tester.error_display


async def test_it_reads_a_named_dispatcher(tester: CommandTester) -> None:
    exit_code = await tester.execute(["--dispatcher", "audit"])

    assert exit_code == 0
    assert "order.refunded" in tester.display
    assert _PLACED not in tester.display


async def test_an_unknown_dispatcher_is_refused(tester: CommandTester) -> None:
    exit_code = await tester.execute(["--dispatcher", "nowhere"])

    assert exit_code != 0
    assert "nowhere" in tester.display + tester.error_display


async def test_outside_debug_mode_the_command_is_not_registered() -> None:
    async with await _kernel(debug=False).boot() as booted:
        assert not booted.container.has(DebugEventDispatcherCommand)


async def test_it_writes_json(tester: CommandTester) -> None:
    exit_code = await tester.execute([_SHIPPED, "--format", "json"])

    assert exit_code == 0
    written = cast("dict[str, list[dict[str, object]]]", json.loads(tester.display))
    assert [listener["priority"] for listener in written[_SHIPPED]] == [0, 0]


async def test_json_with_no_matching_event_is_an_empty_object(tester: CommandTester) -> None:
    exit_code = await tester.execute(["nothing.listens", "--format", "json"])

    assert exit_code == 0
    assert json.loads(tester.display) == {}


async def test_it_writes_markdown(tester: CommandTester) -> None:
    exit_code = await tester.execute([_SHIPPED, "--format", "md"])

    assert exit_code == 0
    assert tester.display.startswith(f"## {_SHIPPED}")
    assert "| #1 |" in tester.display


async def test_it_writes_xml(tester: CommandTester) -> None:
    exit_code = await tester.execute([_SHIPPED, "--format", "xml"])

    assert exit_code == 0
    root = fromstring(tester.display)  # noqa: S314 — the command's own output
    assert [event.get("name") for event in root] == [_SHIPPED]
    assert len(root[0]) == 2


async def test_an_unknown_format_is_refused(tester: CommandTester) -> None:
    exit_code = await tester.execute(["--format", "yaml"])

    assert exit_code != 0
