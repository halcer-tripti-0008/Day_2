"""Pipeline: wires the single-purpose parts together (composition, no inheritance)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .cleaning import TicketCleaner
from .loader import RowSource
from .models import SupportTicket, TicketValidationError
from .validation import TicketValidator


@dataclass(frozen=True)
class RejectedRow:
    line_number: int   # physical line in the file (line 1 is the header)
    reason: str


@dataclass
class PipelineResult:
    tickets: list[SupportTicket] = field(default_factory=list)   # default_factory: NOT a shared list
    rejected: list[RejectedRow] = field(default_factory=list)    # invalid state is explicitly represented


class TicketPipeline:
    def __init__(self, source: RowSource, cleaner: TicketCleaner, validator: TicketValidator) -> None:
        # Dependencies are injected, so tests can pass fakes.
        self._source, self._cleaner, self._validator = source, cleaner, validator

    def run(self) -> PipelineResult:
        result = PipelineResult()
        for row in self._source.rows():
            if row.error is not None:            # structural problem found by the source
                result.rejected.append(RejectedRow(row.line_number, row.error))
                continue
            try:
                result.tickets.append(self._validator.validate(self._cleaner.clean(row.data)))
            except TicketValidationError as exc:
                result.rejected.append(RejectedRow(row.line_number, str(exc)))
        return result
