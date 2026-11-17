import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tickets import (AnalyticsReport, AverageResolutionHours, CountByPriority, CountByStatus,
                     CsvTicketLoader, Priority, SlaBreachRate, Status, SupportTicket,
                     TicketCleaner, TicketPipeline, TicketValidationError, TicketValidator)

T0 = datetime(2025, 1, 1, 9, 0)


def make(**overrides):
    base = dict(ticket_id="T1", customer="Ann", subject="Help", category="General",
                priority=Priority.LOW, status=Status.OPEN, created_at=T0)
    base.update(overrides)
    return SupportTicket(**base)


# ---------- model ----------
def test_valid_open_ticket():
    t = make()
    assert t.resolution_hours is None and not t.is_final


def test_resolution_hours():
    t = make(status=Status.RESOLVED, resolved_at=datetime(2025, 1, 1, 15, 30))
    assert t.resolution_hours == 6.5


@pytest.mark.parametrize("overrides, message", [
    ({"ticket_id": "  "}, "ticket_id"),
    ({"priority": "low"}, "priority must be a Priority"),
    ({"status": Status.RESOLVED}, "requires resolved_at"),
    ({"resolved_at": datetime(2025, 1, 2)}, "must not have resolved_at"),
    ({"status": Status.CLOSED, "resolved_at": datetime(2024, 12, 31)}, "before created_at"),
])
def test_invalid_ticket_is_rejected(overrides, message):
    with pytest.raises(TicketValidationError, match=message):
        make(**overrides)


def test_ticket_is_immutable():
    with pytest.raises(Exception):
        make().status = Status.CLOSED


# ---------- cleaner ----------
def test_cleaner_normalises_text():
    row = {"Priority": " HIGH ", "status": "In Progress", "category": "bILLING", "customer": "  Ben   Cole "}
    out = TicketCleaner().clean(row)
    assert out == {"priority": "high", "status": "in_progress", "category": "Billing", "customer": "Ben Cole"}


def test_cleaner_does_not_mutate_input():
    row = {"priority": " HIGH "}
    TicketCleaner().clean(row)
    assert row == {"priority": " HIGH "}


# ---------- validator ----------
GOOD_ROW = {"ticket_id": "T1", "customer": "Ann", "subject": "Help", "category": "General",
            "priority": "low", "status": "open", "created_at": "2025-01-01 09:00", "resolved_at": ""}


def test_validator_builds_ticket():
    t = TicketValidator().validate(GOOD_ROW)
    assert t.priority is Priority.LOW and t.created_at == T0 and t.resolved_at is None


def test_validator_reports_all_errors_at_once():
    bad = {**GOOD_ROW, "customer": "", "priority": "critical", "created_at": "yesterday"}
    with pytest.raises(TicketValidationError) as exc:
        TicketValidator().validate(bad)
    msg = str(exc.value)
    assert "missing customer" in msg and "invalid priority" in msg and "invalid created_at" in msg


# ---------- loader (real file via tmp_path) ----------
def test_loader_reads_rows(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("ticket_id,customer\nT1,Ann\nT2,Bob\n", encoding="utf-8")
    assert list(CsvTicketLoader(f).rows()) == [
        {"ticket_id": "T1", "customer": "Ann"}, {"ticket_id": "T2", "customer": "Bob"}]


def test_loader_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(CsvTicketLoader(tmp_path / "nope.csv").rows())


# ---------- pipeline (fake source -> no file system needed) ----------
class FakeSource:
    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return iter(self._rows)


def test_pipeline_separates_valid_and_rejected():
    rows = [GOOD_ROW, {**GOOD_ROW, "priority": "nope"}, {**GOOD_ROW, "ticket_id": "T3"}]
    result = TicketPipeline(FakeSource(rows), TicketCleaner(), TicketValidator()).run()
    assert [t.ticket_id for t in result.tickets] == ["T1", "T3"]
    assert [r.line_number for r in result.rejected] == [3]


def test_pipeline_results_do_not_share_state():
    p = TicketPipeline(FakeSource([GOOD_ROW]), TicketCleaner(), TicketValidator())
    a, b = p.run(), p.run()
    assert a.tickets is not b.tickets


# ---------- analytics ----------
def sample_tickets():
    return [
        make(ticket_id="A", priority=Priority.URGENT, status=Status.RESOLVED,
             resolved_at=datetime(2025, 1, 1, 15, 30)),                      # 6.5h  > 4h SLA -> breach
        make(ticket_id="B", priority=Priority.MEDIUM, status=Status.CLOSED,
             resolved_at=datetime(2025, 1, 3, 9, 0)),                        # 48h  <= 72h    -> ok
        make(ticket_id="C", priority=Priority.LOW),                          # open
    ]


def test_existing_metrics_unchanged():
    ts = sample_tickets()
    assert CountByStatus().compute(ts) == {"resolved": 1, "closed": 1, "open": 1}
    assert CountByPriority().compute(ts) == {"urgent": 1, "medium": 1, "low": 1}
    assert AverageResolutionHours().compute(ts) == 27.25


def test_new_metric_sla_breach_rate():
    assert SlaBreachRate().compute(sample_tickets()) == 0.5


def test_sla_custom_config_and_isolation():
    m = SlaBreachRate({Priority.URGENT: 10, Priority.MEDIUM: 10})
    assert m.compute(sample_tickets()) == 0.5          # B now breaches, A no longer does
    assert SlaBreachRate.DEFAULT_SLA_HOURS[Priority.URGENT] == 4   # default untouched


def test_metrics_handle_no_data():
    assert AverageResolutionHours().compute([]) is None
    assert SlaBreachRate().compute([make()]) is None


def test_report_composes_metrics():
    out = AnalyticsReport([CountByStatus(), SlaBreachRate()]).run(sample_tickets())
    assert set(out) == {"count_by_status", "sla_breach_rate"}
