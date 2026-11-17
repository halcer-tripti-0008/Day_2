"""CSV loading (Task B).

Responsibility: turn a CSV file into raw dict rows. Nothing else.
It does not clean, validate or interpret values.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Protocol

RawRow = dict[str, str]


class RowSource(Protocol):
    """Anything that yields raw rows. The pipeline depends on this, not on CSV."""

    def rows(self) -> Iterator[RawRow]: ...


class CsvTicketLoader:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)  # instance state: each loader has its own file

    def rows(self) -> Iterator[RawRow]:
        with self._path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                yield dict(row)
