"""Analytics (Tasks B and C).

Responsibility: compute numbers from already-valid tickets.

Design: every metric is a tiny class with `name` and `compute(tickets)`
(the `Metric` protocol). `AnalyticsReport` *composes* metrics. Adding a new
metric = adding a new class; nothing existing is edited (open/closed).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .models import Priority, SupportTicket


class Metric(Protocol):
    name: str

    def compute(self, tickets: Sequence[SupportTicket]) -> Any: ...


class CountByStatus:
    name = "count_by_status"

    def compute(self, tickets):
        return dict(Counter(t.status.value for t in tickets))


class CountByPriority:
    name = "count_by_priority"

    def compute(self, tickets):
        return dict(Counter(t.priority.value for t in tickets))


class AverageResolutionHours:
    name = "avg_resolution_hours"

    def compute(self, tickets):
        hours = [t.resolution_hours for t in tickets if t.resolution_hours is not None]
        return round(sum(hours) / len(hours), 2) if hours else None


# ---- Task C: NEW operation, added without touching the classes above ----
class SlaBreachRate:
    """Share of resolved tickets that took longer than the SLA for their priority."""

    name = "sla_breach_rate"
    DEFAULT_SLA_HOURS: Mapping[Priority, float] = {   # shared, read-only by convention
        Priority.URGENT: 4, Priority.HIGH: 24, Priority.MEDIUM: 72, Priority.LOW: 120,
    }

    def __init__(self, sla_hours: Mapping[Priority, float] | None = None) -> None:
        # Copy -> each instance owns its config; callers can't mutate the default.
        self._sla = dict(sla_hours or self.DEFAULT_SLA_HOURS)

    def compute(self, tickets):
        resolved = [t for t in tickets if t.resolution_hours is not None]
        if not resolved:
            return None
        breached = sum(1 for t in resolved if t.resolution_hours > self._sla[t.priority])
        return round(breached / len(resolved), 2)


class AnalyticsReport:
    def __init__(self, metrics: Iterable[Metric]) -> None:
        self._metrics = list(metrics)

    def run(self, tickets: Sequence[SupportTicket]) -> dict[str, Any]:
        return {m.name: m.compute(tickets) for m in self._metrics}
