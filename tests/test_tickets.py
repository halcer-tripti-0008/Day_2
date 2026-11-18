import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tickets import (DAY01_SCHEMA, DAY02_SCHEMA, AnalyticsReport, AverageCustomerRating,  # noqa: E402
                     AverageResolutionByCategory, AverageResolutionHours, CountByPriority,
                     CountByStatus, CsvTicketLoader, MalformedCsvError, Priority, SlaBreachRate,
                     SourceRow, Status, SupportTicket, TicketCleaner, TicketPipeline,
                     TicketValidationError, TicketValidator, UnresolvedCount, detect_schema)

T0 = datetime(2025, 1, 1, 9, 0)
DAY01_CSV = ROOT / "data" / "day01_tickets.csv"
DAY02_CSV = ROOT / "data" / "tickets.csv"


def make(**overrides):
    base = dict(ticket_id="T1", category="General", priority=Priority.LOW,
                status=Status.OPEN, customer="Ann", subject="Help", created_at=T0)
    base.update(overrides)
    return SupportTicket(**base)


def write_csv(tmp_path, text, name="t.csv"):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return f


def run_pipeline(path, schema):
    return TicketPipeline(CsvTicketLoader(path), TicketCleaner(), TicketValidator(schema)).run()


# =============== model ===============
def test_valid_open_ticket():
    t = make()
    assert t.resolution_hours is None and not t.is_final


def test_resolution_hours_from_timestamps():
    t = make(status=Status.RESOLVED, resolved_at=datetime(2025, 1, 1, 15, 30))
    assert t.resolution_hours == 6.5


def test_resolution_hours_from_day01_field():
    t = SupportTicket(ticket_id="D1", category="Billing", priority=Priority.HIGH,
                      status=Status.RESOLVED, resolution_time_hours=5.5, customer_rating=4)
    assert t.resolution_hours == 5.5


@pytest.mark.parametrize("overrides, message", [
    ({"ticket_id": "  "}, "ticket_id"),
    ({"priority": "low"}, "priority must be a Priority"),
    ({"status": Status.RESOLVED}, "requires resolved_at or resolution_time_hours"),
    ({"resolved_at": datetime(2025, 1, 2)}, "must not have resolved_at"),
    ({"status": Status.CLOSED, "resolved_at": datetime(2024, 12, 31)}, "before created_at"),
    ({"resolution_time_hours": -1}, "resolution_time_hours"),
    ({"resolution_time_hours": float("nan")}, "resolution_time_hours"),
    ({"customer_rating": 9}, "customer_rating"),
    ({"customer_rating": True}, "customer_rating"),
])
def test_invalid_ticket_is_rejected(overrides, message):
    with pytest.raises(TicketValidationError, match=message):
        make(**overrides)


def test_resolved_at_requires_created_at():
    with pytest.raises(TicketValidationError, match="requires created_at"):
        make(created_at=None, status=Status.RESOLVED, resolved_at=T0)


def test_ticket_is_immutable():
    with pytest.raises(Exception):
        make().status = Status.CLOSED


# =============== cleaner ===============
def test_cleaner_normalises_text():
    row = {"Priority": " HIGH ", "status": "In Progress", "category": "bILLING", "customer": "  Ben   Cole "}
    out = TicketCleaner().clean(row)
    assert out == {"priority": "high", "status": "in_progress", "category": "Billing", "customer": "Ben Cole"}


def test_cleaner_does_not_mutate_input():
    row = {"priority": " HIGH "}
    TicketCleaner().clean(row)
    assert row == {"priority": " HIGH "}


# =============== validator ===============
GOOD_ROW = {"ticket_id": "T1", "customer": "Ann", "subject": "Help", "category": "General",
            "priority": "low", "status": "open", "created_at": "2025-01-01 09:00", "resolved_at": ""}
GOOD_DAY01_ROW = {"ticket_id": "D1", "category": "Billing", "priority": "high", "description": "x",
                  "status": "resolved", "resolution_time_hours": "5.5", "customer_rating": "4"}


def test_validator_builds_ticket():
    t = TicketValidator().validate(GOOD_ROW)
    assert t.priority is Priority.LOW and t.created_at == T0 and t.resolved_at is None


def test_validator_reports_all_errors_at_once():
    bad = {**GOOD_ROW, "customer": "", "priority": "critical", "created_at": "yesterday"}
    with pytest.raises(TicketValidationError) as exc:
        TicketValidator().validate(bad)
    msg = str(exc.value)
    assert "missing customer" in msg and "invalid priority" in msg and "invalid created_at" in msg


def test_day01_row_accepted_by_day01_schema():
    t = TicketValidator(DAY01_SCHEMA).validate(GOOD_DAY01_ROW)
    assert (t.resolution_hours, t.customer_rating) == (5.5, 4)


def test_day01_row_rejected_by_day02_schema_with_clear_reason():
    with pytest.raises(TicketValidationError, match="missing customer; missing subject; missing created_at"):
        TicketValidator(DAY02_SCHEMA).validate(GOOD_DAY01_ROW)


@pytest.mark.parametrize("field, value, message", [
    ("resolution_time_hours", "abc", "not a number"),
    ("customer_rating", "4.5", "not an integer"),
    ("customer_rating", "9", "customer_rating must be an integer 1-5"),
])
def test_validator_rejects_bad_legacy_numbers(field, value, message):
    with pytest.raises(TicketValidationError, match=message):
        TicketValidator(DAY01_SCHEMA).validate({**GOOD_DAY01_ROW, field: value})


def test_detect_schema():
    assert detect_schema(["ticket_id", "created_at"]) is DAY02_SCHEMA
    assert detect_schema(["ticket_id", "resolution_time_hours"]) is DAY01_SCHEMA


# =============== loader ===============
def test_loader_reads_rows(tmp_path):
    f = write_csv(tmp_path, "ticket_id,customer\nT1,Ann\nT2,Bob\n")
    rows = list(CsvTicketLoader(f).rows())
    assert [(r.line_number, r.data) for r in rows] == [
        (2, {"ticket_id": "T1", "customer": "Ann"}), (3, {"ticket_id": "T2", "customer": "Bob"})]


def test_loader_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(CsvTicketLoader(tmp_path / "nope.csv").rows())


def test_loader_skips_blank_lines_and_handles_bom(tmp_path):
    f = tmp_path / "t.csv"
    f.write_bytes("﻿ticket_id,customer\n\nT1,Ann\n".encode("utf-8"))
    rows = list(CsvTicketLoader(f).rows())
    assert len(rows) == 1 and rows[0].data == {"ticket_id": "T1", "customer": "Ann"}


def test_loader_normalises_header_names(tmp_path):
    f = write_csv(tmp_path, " Ticket_ID , CUSTOMER\nT1,Ann\n")
    assert CsvTicketLoader(f).header() == ["ticket_id", "customer"]


# ---- B2 regression: extra / missing fields must not crash or shift fields ----
def test_B2_extra_fields_are_rejected_not_a_crash(tmp_path):
    f = write_csv(tmp_path, "ticket_id,customer\nT1,Ann,extra,more\nT2,Bob\n")
    rows = list(CsvTicketLoader(f).rows())
    assert rows[0].data is None and "expected 2 fields, found 4" in rows[0].error
    assert rows[1].data == {"ticket_id": "T2", "customer": "Bob"}   # later rows still processed


def test_B2_short_record_is_rejected(tmp_path):
    f = write_csv(tmp_path, "ticket_id,customer\nT1\n")
    (row,) = CsvTicketLoader(f).rows()
    assert "expected 2 fields, found 1" in row.error


def test_B2_pipeline_end_to_end_with_extra_fields(tmp_path):
    header = "ticket_id,customer,subject,category,priority,status,created_at,resolved_at\n"
    f = write_csv(tmp_path, header
                  + "T1,Ann,Help,General,low,open,2025-01-01 09:00,,EXTRA\n"
                  + "T2,Bob,Help,General,low,open,2025-01-01 09:00,\n")
    result = run_pipeline(f, DAY02_SCHEMA)       # must not raise AttributeError
    assert [t.ticket_id for t in result.tickets] == ["T2"]
    assert result.rejected[0].line_number == 2 and "malformed record" in result.rejected[0].reason


# ---- B3 regression: duplicate / empty normalised headers ----
def test_B3_duplicate_status_columns_are_rejected(tmp_path):
    f = write_csv(tmp_path, "ticket_id,status, status\nT1,closed,open\n")
    with pytest.raises(MalformedCsvError, match="duplicate column name.*status"):
        list(CsvTicketLoader(f).rows())


def test_B3_duplicate_status_cannot_change_an_accepted_ticket(tmp_path):
    header = "ticket_id,customer,subject,category,priority,status, status,created_at\n"
    f = write_csv(tmp_path, header + "T1,Ann,Help,General,low,closed,open,2025-01-01 09:00\n")
    with pytest.raises(MalformedCsvError):
        run_pipeline(f, DAY02_SCHEMA)


def test_B3_case_variants_are_duplicates(tmp_path):
    f = write_csv(tmp_path, "Status,STATUS\nopen,closed\n")
    with pytest.raises(MalformedCsvError, match="duplicate"):
        CsvTicketLoader(f).header()


def test_B3_empty_header_name_rejected(tmp_path):
    f = write_csv(tmp_path, "ticket_id,,status\nT1,x,open\n")
    with pytest.raises(MalformedCsvError, match="empty column name"):
        CsvTicketLoader(f).header()


def test_empty_file_rejected(tmp_path):
    with pytest.raises(MalformedCsvError, match="empty"):
        CsvTicketLoader(write_csv(tmp_path, "")).header()


# =============== pipeline (fake source -> no file system needed) ===============
class FakeSource:
    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return iter(SourceRow(i, data=r) for i, r in enumerate(self._rows, start=2))


def test_pipeline_separates_valid_and_rejected():
    rows = [GOOD_ROW, {**GOOD_ROW, "priority": "nope"}, {**GOOD_ROW, "ticket_id": "T3"}]
    result = TicketPipeline(FakeSource(rows), TicketCleaner(), TicketValidator()).run()
    assert [t.ticket_id for t in result.tickets] == ["T1", "T3"]
    assert [r.line_number for r in result.rejected] == [3]


def test_pipeline_results_do_not_share_state():
    p = TicketPipeline(FakeSource([GOOD_ROW]), TicketCleaner(), TicketValidator())
    a, b = p.run(), p.run()
    assert a.tickets is not b.tickets


# =============== B1 regression: Day 01 data contract still works ===============
def test_B1_day01_file_is_loaded_with_day01_schema():
    result = run_pipeline(DAY01_CSV, DAY01_SCHEMA)
    assert len(result.tickets) == 6
    assert {r.line_number for r in result.rejected} == {8, 9, 10}   # extra fields, bad priority, bad rating


def test_B1_two_valid_day01_records_are_accepted(tmp_path):
    f = write_csv(tmp_path, "ticket_id,category,priority,description,resolution_time_hours,customer_rating,status\n"
                            "A,Billing,high,d,4,5,resolved\nB,Billing,low,d,,,open\n")
    result = run_pipeline(f, detect_schema(CsvTicketLoader(f).header()))
    assert (len(result.tickets), len(result.rejected)) == (2, 0)


def test_B1_day01_analytics_values():
    t = run_pipeline(DAY01_CSV, DAY01_SCHEMA).tickets
    assert CountByPriority().compute(t) == {"high": 1, "medium": 2, "low": 2, "urgent": 1}
    assert CountByStatus().compute(t) == {"resolved": 3, "closed": 1, "open": 2}
    assert AverageResolutionHours().compute(t) == pytest.approx(12.375, abs=0.01)
    assert AverageResolutionByCategory().compute(t) == {"Account": 2.0, "Billing": 17.75, "Technical": 12.0}
    assert AverageCustomerRating().compute(t) == 4.0      # ratings 4, 3, 5; blanks ignored
    assert UnresolvedCount().compute(t) == 2
    assert SlaBreachRate().compute(t) == 0.0


def test_B1_cli_runs_on_old_and_new_datasets():
    for path, schema in ((DAY01_CSV, "day01"), (DAY02_CSV, "day02")):
        out = subprocess.run([sys.executable, str(ROOT / "main.py"), str(path)],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert f"Schema: {schema}" in out.stdout


def test_cli_reports_malformed_header_without_traceback(tmp_path):
    f = write_csv(tmp_path, "ticket_id,status, status\nT1,closed,open\n")
    out = subprocess.run([sys.executable, str(ROOT / "main.py"), str(f)], capture_output=True, text=True)
    assert out.returncode == 1 and "duplicate column name" in out.stderr and "Traceback" not in out.stderr


def test_cli_reports_missing_columns(tmp_path):
    f = write_csv(tmp_path, "ticket_id,priority\nT1,low\n")
    out = subprocess.run([sys.executable, str(ROOT / "main.py"), str(f)], capture_output=True, text=True)
    assert out.returncode == 1 and "missing required column" in out.stderr


# =============== analytics (Day 02 data) ===============
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
    full = {Priority.URGENT: 10, Priority.HIGH: 10, Priority.MEDIUM: 10, Priority.LOW: 10}
    assert SlaBreachRate(full).compute(sample_tickets()) == 0.5     # B now breaches, A no longer does
    assert SlaBreachRate.DEFAULT_SLA_HOURS[Priority.URGENT] == 4    # default untouched


def test_sla_default_is_read_only():
    with pytest.raises(TypeError):
        SlaBreachRate.DEFAULT_SLA_HOURS[Priority.URGENT] = 999


@pytest.mark.parametrize("config, message", [
    ({Priority.URGENT: 4}, "missing priorities"),                                   # partial mapping
    ({**SlaBreachRate.DEFAULT_SLA_HOURS, Priority.LOW: 0}, "positive numbers"),
    ({**SlaBreachRate.DEFAULT_SLA_HOURS, Priority.LOW: "fast"}, "positive numbers"),
    ({**SlaBreachRate.DEFAULT_SLA_HOURS, "bogus": 5}, "Priority"),
])
def test_sla_config_is_validated_up_front(config, message):
    with pytest.raises(ValueError, match=message):
        SlaBreachRate(config)


def test_metrics_handle_no_data():
    assert AverageResolutionHours().compute([]) is None
    assert AverageCustomerRating().compute([]) is None
    assert SlaBreachRate().compute([make()]) is None


def test_report_composes_metrics():
    out = AnalyticsReport([CountByStatus(), SlaBreachRate()]).run(sample_tickets())
    assert set(out) == {"count_by_status", "sla_breach_rate"}
