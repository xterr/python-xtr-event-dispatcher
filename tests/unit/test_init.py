from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import xtr_event_dispatcher


def test_the_version_is_the_one_pyproject_declares() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    data = cast(
        "dict[str, dict[str, object]]",
        tomllib.loads(pyproject.read_text(encoding="utf-8")),
    )

    assert xtr_event_dispatcher.__version__ == data["project"]["version"]


def test_every_exported_name_resolves() -> None:
    missing = [
        name for name in xtr_event_dispatcher.__all__ if not hasattr(xtr_event_dispatcher, name)
    ]

    assert missing == []
