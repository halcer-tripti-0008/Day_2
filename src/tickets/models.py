"""Domain model (Task A).

Responsibility: describe what a valid support ticket *is*.
No file I/O, no cleaning, no analytics.
"""
from __future__ import annotations

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


@dataclass(frozen=True)
class SupportTicket:
    """An immutable, always-valid ticket.

    frozen=True  -> fields cannot be changed after creation.
    __post_init__ -> an invalid ticket can never exist (fail at construction).
    """

    # Class-level state: shared by every instance, immutable (frozenset) on purpose.
    FINAL_STATUSES = frozenset({Status.RESOLVED, Status.CLOSED})

    ticket_id: str
    customer: str
    subject: str
    category: str
    priority: Priority
    status: Status
    created_at: datetime
    resolved_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        errors: list[str] = []
        for name in ("ticket_id", "customer", "subject", "category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{name} must be a non-empty string")
        if not isinstance(self.priority, Priority):
            errors.append("priority must be a Priority")
        if not isinstance(self.status, Status):
            errors.append("status must be a Status")
        if not isinstance(self.created_at, datetime):
            errors.append("created_at must be a datetime")
        if self.resolved_at is not None and not isinstance(self.resolved_at, datetime):
            errors.append("resolved_at must be a datetime or None")

        # Cross-field rules only make sense once the types above are right.
        if not errors:
            if self.status in self.FINAL_STATUSES and self.resolved_at is None:
                errors.append(f"status '{self.status.value}' requires resolved_at")
            if self.status not in self.FINAL_STATUSES and self.resolved_at is not None:
                errors.append(f"status '{self.status.value}' must not have resolved_at")
            if self.resolved_at is not None and self.resolved_at < self.created_at:
                errors.append("resolved_at cannot be before created_at")

        if errors:
            raise TicketValidationError("; ".join(errors))

    @property
    def is_final(self) -> bool:
        return self.status in self.FINAL_STATUSES

    @property
    def resolution_hours(self) -> Optional[float]:
        """Hours from creation to resolution, or None if not resolved yet."""
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.created_at).total_seconds() / 3600
