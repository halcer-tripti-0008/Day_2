# Resubmission notes (review FAIL 2026-11-18)

| Defect | Fix | Regression tests |
|---|---|---|
| B1 Day 01 compatibility (P0) | One model with Day 01 core fields + optional Day 02 fields; `TicketSchema` (`day01`/`day02`) + auto-detection; Day 01 metrics restored as classes (`AverageResolutionByCategory`, `AverageCustomerRating`, `UnresolvedCount`); `SlaBreachRate` stays additive | `test_B1_*` (7-column file accepted, analytics values, CLI on both datasets) |
| B2 Extra CSV fields crash (P0) | Loader uses `csv.reader`, rejects any record whose field count differs from the header as a `SourceRow(error=...)`; cleaner can no longer receive a list | `test_B2_*` |
| B3 Duplicate normalised headers (P1) | Loader normalises headers first and raises `MalformedCsvError` on empty/duplicate names; CLI prints error, exit 1 | `test_B3_*`, `test_cli_*` |
| Non-blocking: SLA defaults | `MappingProxyType` default; config validated in `__init__` (all priorities, positive numbers) | `test_sla_*` |

Tests: 54 passed (`docs/test_output.txt`). The original 21 tests are all still present; 4 were adjusted for intentional changes (loader yields `SourceRow`, new "requires resolved_at or resolution_time_hours" message, SLA partial config now rejected up front).
Caveat: the original approved Day 01 CSV was not available here, so `data/day01_tickets.csv` is a representative stand-in built from the field list in the review. Run `python3 main.py <original day01 file>` to confirm.
