"""Analytics (Tasks B and C).

Responsibility: compute numbers from already-valid tickets.

Design: every metric is a tiny class with `name` and `compute(tickets)`
(the `Metric` protocol). `AnalyticsReport` *composes* metrics. Adding a new
metric = adding a new class; nothing existing is edited (open/closed).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .models import Priority, SupportTicket


class Metric(Protocol):
    name: str

    def compute(self, tickets: Sequence[SupportTicket]) -> Any: ...


def _mean(values: list[float]):
    return round(sum(values) / len(values), 2) if values else None


# ---- Day 01 behaviours (preserved) ----
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
        return _mean([t.resolution_hours for t in tickets if t.resolution_hours is not None])


class AverageResolutionByCategory:
    """Mean resolution hours per category (categories with no resolved ticket are omitted)."""
    name = "avg_resolution_hours_by_category"

    def compute(self, tickets):
        groups: dict[str, list[float]] = defaultdict(list)
        for t in tickets:
            if t.resolution_hours is not None:
                groups[t.category].append(t.resolution_hours)
        return {category: _mean(hours) for category, hours in sorted(groups.items())}


class AverageCustomerRating:
    name = "avg_customer_rating"

    def compute(self, tickets):
        return _mean([t.customer_rating for t in tickets if t.customer_rating is not None])


class UnresolvedCount:
    """Tickets whose status is not resolved/closed."""
    name = "unresolved_count"

    def compute(self, tickets):
        return sum(1 for t in tickets if not t.is_final)


# ---- Task C: NEW operation, added without touching the classes above ----
class SlaBreachRate:
    """Share of resolved tickets that took longer than the SLA for their priority."""

    name = "sla_breach_rate"
    # Read-only view: nobody can change the shared default by accident.
    DEFAULT_SLA_HOURS: Mapping[Priority, float] = MappingProxyType({
        Priority.URGENT: 4, Priority.HIGH: 24, Priority.MEDIUM: 72, Priority.LOW: 120,
    })

    def __init__(self, sla_hours: Mapping[Priority, float] | None = None) -> None:
        # Copy -> each instance owns its config; validated up front, not at compute time.
        config = dict(self.DEFAULT_SLA_HOURS if sla_hours is None else sla_hours)
        bad_keys = [k for k in config if not isinstance(k, Priority)]
        if bad_keys:
            raise ValueError(f"SLA keys must be Priority values, got: {bad_keys}")
        missing = [p.value for p in Priority if p not in config]
        if missing:
            raise ValueError(f"SLA config missing priorities: {', '.join(missing)}")
        bad_values = [p.value for p, h in config.items()
                      if isinstance(h, bool) or not isinstance(h, (int, float)) or not h > 0]
        if bad_values:
            raise ValueError(f"SLA hours must be positive numbers for: {', '.join(bad_values)}")
        self._sla = config

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
