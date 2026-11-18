"""CSV loading (Task B).

Responsibility: turn a CSV file into raw rows, safely. It does not clean values
or apply business rules, but it DOES guarantee structural integrity:

* header names are trimmed/lower-cased; empty or duplicate names -> MalformedCsvError
  (so two columns can never silently collapse into one and overwrite each other)
* a record whose field count differs from the header is returned as a rejected
  row (never mapped by position, never crashing later stages)
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Protocol

RawRow = dict[str, str]


class MalformedCsvError(ValueError):
    """The file as a whole cannot be read (empty, bad/duplicate header)."""


@dataclass(frozen=True)
class SourceRow:
    """One record from a source: either `data` or an `error`, never both."""
    line_number: int
    data: Optional[RawRow] = None
    error: Optional[str] = None


class RowSource(Protocol):
    """Anything that yields SourceRows. The pipeline depends on this, not on CSV."""

    def rows(self) -> Iterator[SourceRow]: ...


class CsvTicketLoader:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)  # instance state: each loader has its own file

    def header(self) -> list[str]:
        """Validated, normalised column names (used to pick a schema)."""
        with self._open() as fh:
            return self._read_header(csv.reader(fh))

    def rows(self) -> Iterator[SourceRow]:
        with self._open() as fh:
            reader = csv.reader(fh)
            header = self._read_header(reader)
            for fields in reader:
                if not fields:               # truly blank line
                    continue
                line_no = reader.line_num
                if len(fields) != len(header):
                    yield SourceRow(
                        line_no,
                        error=f"malformed record: expected {len(header)} fields, found {len(fields)}",
                    )
                    continue
                yield SourceRow(line_no, data=dict(zip(header, fields)))

    # -- helpers --
    def _open(self):
        # utf-8-sig silently drops a BOM so the first header isn't "﻿ticket_id"
        return self._path.open(newline="", encoding="utf-8-sig")

    @staticmethod
    def _read_header(reader) -> list[str]:
        raw = next(reader, None)
        if not raw:
            raise MalformedCsvError("file is empty or has no header row")
        header = [h.strip().lower() for h in raw]
        empty = [i + 1 for i, h in enumerate(header) if not h]
        if empty:
            raise MalformedCsvError(f"empty column name at position(s) {empty}")
        seen, dupes = set(), []
        for h in header:
            if h in seen and h not in dupes:
                dupes.append(h)
            seen.add(h)
        if dupes:
            raise MalformedCsvError(
                f"duplicate column name(s) after trim/case normalisation: {', '.join(dupes)}")
        return header
