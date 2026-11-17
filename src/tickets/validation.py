"""Validation (Task B).

Responsibility: decide whether a cleaned row is acceptable and, if so,
convert it into a SupportTicket. Invalid rows raise TicketValidationError
listing *every* problem (not just the first).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .loader import RawRow
from .models import Priority, Status, SupportTicket, TicketValidationError


class TicketValidator:
    REQUIRED_FIELDS = ("ticket_id", "customer", "subject", "category",
                       "priority", "status", "created_at")
    DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")

    def validate(self, row: RawRow) -> SupportTicket:
        errors: list[str] = []

        for name in self.REQUIRED_FIELDS:
            if not row.get(name):
                errors.append(f"missing {name}")

        priority = self._enum(Priority, row.get("priority"), "priority", errors)
        status = self._enum(Status, row.get("status"), "status", errors)
        created_at = self._date(row.get("created_at"), "created_at", errors)
        resolved_at = self._date(row.get("resolved_at"), "resolved_at", errors, optional=True)

        if errors:
            raise TicketValidationError("; ".join(errors))

        # The model re-checks its own invariants (e.g. resolved_at >= created_at).
        return SupportTicket(
            ticket_id=row["ticket_id"], customer=row["customer"],
            subject=row["subject"], category=row["category"],
            priority=priority, status=status,
            created_at=created_at, resolved_at=resolved_at,
        )

    @staticmethod
    def _enum(enum_cls, value: Optional[str], name: str, errors: list[str]):
        if not value:
            return None  # already reported as missing
        try:
            return enum_cls(value)
        except ValueError:
            allowed = ", ".join(m.value for m in enum_cls)
            errors.append(f"invalid {name} '{value}' (allowed: {allowed})")
            return None

    def _date(self, value: Optional[str], name: str, errors: list[str],
              optional: bool = False) -> Optional[datetime]:
        if not value:
            if not optional:
                pass  # missing already reported
            return None
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        errors.append(f"invalid {name} '{value}'")
        return None
