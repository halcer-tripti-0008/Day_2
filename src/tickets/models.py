"""Domain model (Task A).

Responsibility: describe what a valid support ticket *is*.
No file I/O, no cleaning, no analytics.

One model serves both data contracts:
  * Core / Day 01 fields : ticket_id, category, priority, description, status,
                           resolution_time_hours, customer_rating
  * Extended / Day 02    : customer, subject, created_at, resolved_at
Which fields a *file* must contain is decided by a TicketSchema (validation.py),
not by the model, so legacy Day 01 data stays loadable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TicketValidationError(ValueError):
    """Raised when data cannot form a valid SupportTicket."""


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class SupportTicket:
    """An immutable, always-valid ticket (invalid tickets cannot be constructed)."""

    # Class-level state: shared by every instance, immutable (frozenset) on purpose.
    FINAL_STATUSES = frozenset({Status.RESOLVED, Status.CLOSED})
    MIN_RATING = 1
    MAX_RATING = 5

    # --- core (Day 01) fields ---
    ticket_id: str
    category: str
    priority: Priority
    status: Status
    description: str = ""
    resolution_time_hours: Optional[float] = None
    customer_rating: Optional[int] = None
    # --- extended (Day 02) fields, all optional ---
    customer: Optional[str] = None
    subject: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        errors: list[str] = []
        for name in ("ticket_id", "category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        for name in ("description", "customer", "subject"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                errors.append(f"{name} must be a string or None")
        if not isinstance(self.priority, Priority):
            errors.append("priority must be a Priority")
        if not isinstance(self.status, Status):
            errors.append("status must be a Status")

        hours = self.resolution_time_hours
        if hours is not None and not (_is_number(hours) and math.isfinite(hours) and hours >= 0):
            errors.append("resolution_time_hours must be a finite number >= 0 or None")

        rating = self.customer_rating
        if rating is not None and not (
            isinstance(rating, int) and not isinstance(rating, bool)
            and self.MIN_RATING <= rating <= self.MAX_RATING
        ):
            errors.append(f"customer_rating must be an integer {self.MIN_RATING}-{self.MAX_RATING} or None")

        for name in ("created_at", "resolved_at"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, datetime):
                errors.append(f"{name} must be a datetime or None")

        # Cross-field rules only make sense once the types above are right.
        if not errors:
            has_resolution = self.resolved_at is not None or self.resolution_time_hours is not None
            if self.status in self.FINAL_STATUSES and not has_resolution:
                errors.append(f"status '{self.status.value}' requires resolved_at or resolution_time_hours")
            if self.status not in self.FINAL_STATUSES and self.resolved_at is not None:
                errors.append(f"status '{self.status.value}' must not have resolved_at")
            if self.resolved_at is not None and self.created_at is None:
                errors.append("resolved_at requires created_at")
            if (self.resolved_at is not None and self.created_at is not None
                    and self.resolved_at < self.created_at):
                errors.append("resolved_at cannot be before created_at")

        if errors:
            raise TicketValidationError("; ".join(errors))

    @property
    def is_final(self) -> bool:
        return self.status in self.FINAL_STATUSES

    @property
    def resolution_hours(self) -> Optional[float]:
        """Hours to resolve: the stated value if present, else computed from timestamps, else None."""
        if self.resolution_time_hours is not None:
            return float(self.resolution_time_hours)
        if self.resolved_at is not None and self.created_at is not None:
            return (self.resolved_at - self.created_at).total_seconds() / 3600
        return None
