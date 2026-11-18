"""Validation (Task B).

Responsibility: decide whether a cleaned row is acceptable under a given
TicketSchema and, if so, convert it into a SupportTicket. Invalid rows raise
TicketValidationError listing *every* problem (not just the first).

Schemas are the explicit compatibility layer between data contracts:
  DAY01_SCHEMA : ticket_id, category, priority, description, status
                 (+ optional resolution_time_hours, customer_rating)
  DAY02_SCHEMA : ticket_id, customer, subject, category, priority, status, created_at
                 (+ optional resolved_at, resolution_time_hours, customer_rating)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from .loader import RawRow
from .models import Priority, Status, SupportTicket, TicketValidationError


@dataclass(frozen=True)
class TicketSchema:
    name: str
    required_fields: tuple[str, ...]

    def missing_columns(self, header: Sequence[str]) -> list[str]:
        return [f for f in self.required_fields if f not in header]


DAY01_SCHEMA = TicketSchema("day01", ("ticket_id", "category", "priority", "description", "status"))
DAY02_SCHEMA = TicketSchema("day02", ("ticket_id", "customer", "subject", "category",
                                      "priority", "status", "created_at"))
SCHEMAS = {s.name: s for s in (DAY01_SCHEMA, DAY02_SCHEMA)}


def detect_schema(header: Sequence[str]) -> TicketSchema:
    """Day 02 files carry created_at; anything else is treated as Day 01."""
    return DAY02_SCHEMA if "created_at" in header else DAY01_SCHEMA


class TicketValidator:
    DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")

    def __init__(self, schema: TicketSchema = DAY02_SCHEMA) -> None:
        self._schema = schema

    def validate(self, row: RawRow) -> SupportTicket:
        errors: list[str] = []

        for name in self._schema.required_fields:
            if not row.get(name):
                errors.append(f"missing {name}")

        priority = self._enum(Priority, row.get("priority"), "priority", errors)
        status = self._enum(Status, row.get("status"), "status", errors)
        hours = self._number(row.get("resolution_time_hours"), "resolution_time_hours", errors)
        rating = self._integer(row.get("customer_rating"), "customer_rating", errors)
        created_at = self._date(row.get("created_at"), "created_at", errors)
        resolved_at = self._date(row.get("resolved_at"), "resolved_at", errors)

        if errors:
            raise TicketValidationError("; ".join(errors))

        # The model re-checks its own invariants (ranges, cross-field rules).
        return SupportTicket(
            ticket_id=row["ticket_id"], category=row["category"],
            priority=priority, status=status,
            description=row.get("description", ""),
            resolution_time_hours=hours, customer_rating=rating,
            customer=row.get("customer") or None, subject=row.get("subject") or None,
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

    @staticmethod
    def _number(value: Optional[str], name: str, errors: list[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            errors.append(f"invalid {name} '{value}' (not a number)")
            return None

    @staticmethod
    def _integer(value: Optional[str], name: str, errors: list[str]) -> Optional[int]:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            errors.append(f"invalid {name} '{value}' (not an integer)")
            return None

    def _date(self, value: Optional[str], name: str, errors: list[str]) -> Optional[datetime]:
        if not value:
            return None  # required-ness is the schema's job
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        errors.append(f"invalid {name} '{value}'")
        return None
