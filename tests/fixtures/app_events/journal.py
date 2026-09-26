from __future__ import annotations

from xtr_dependency_injection import as_service


@as_service
class Journal:
    """What every listener of the application writes to, so a test can read what ran."""

    def __init__(self) -> None:
        self.entries: list[str] = []
