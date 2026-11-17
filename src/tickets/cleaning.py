"""Cleaning (Task B).

Responsibility: normalise the *text* of a raw row (whitespace, case).
It never rejects data and never builds domain objects.
"""
from __future__ import annotations

from .loader import RawRow


class TicketCleaner:
    # Class-level config: immutable tuples, so sharing is safe.
    LOWERCASE_FIELDS = ("priority", "status")
    TITLE_FIELDS = ("category",)

    def clean(self, row: RawRow) -> RawRow:
        cleaned: RawRow = {}
        for key, value in row.items():
            key = (key or "").strip().lower()
            value = " ".join((value or "").split())  # trim + collapse whitespace
            if key in self.LOWERCASE_FIELDS:
                value = value.lower().replace(" ", "_").replace("-", "_")
            elif key in self.TITLE_FIELDS:
                value = value.title()
            cleaned[key] = value
        return cleaned
