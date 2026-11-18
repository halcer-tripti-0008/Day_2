# Support Ticket Processor (Day 02 refactor)

Small reusable components that load, clean, validate and analyse support tickets from a CSV.

## Setup
```bash
python3 -m pip install pytest      # only dependency (Python 3.10+)
python3 main.py                              # Day 02 sample (data/tickets.csv)
python3 main.py data/day01_tickets.csv       # Day 01 (7-column) data
python3 main.py path/to/file.csv [--schema auto|day01|day02]
python3 -m pytest -v                         # 54 tests
```

## Structure and why responsibilities are separated
| Module | One responsibility | Knows nothing about |
|---|---|---|
| `models.py` | What a valid `SupportTicket` is (frozen dataclass, validates in `__post_init__`) | files, CSV, analytics |
| `loader.py` | CSV file -> raw rows; guarantees structure (valid header, correct field count) | cleaning, business rules |
| `cleaning.py` | Normalise text (trim, case) | rejecting rows |
| `validation.py` | Raw row -> `SupportTicket` (per `TicketSchema`) or a list of every error | file formats |
| `analytics.py` | Numbers from valid tickets (one class per metric) | where tickets came from |
| `pipeline.py` | Wires loader -> cleaner -> validator; returns valid tickets + rejected rows | metric maths |

Why this is maintainable
- **Change one thing, touch one file.** A new CSV column rule lives in validation only; a new file format means a new `RowSource`.
- **Testable.** The pipeline takes a `RowSource`, so tests inject an in-memory fake instead of a real file.
- **Composition over inheritance.** There is no inheritance. `TicketPipeline` and `AnalyticsReport` *hold* the parts they use. Protocols (`RowSource`, `Metric`) define the interfaces.
- **Extending without breaking.** `SlaBreachRate` (Task C) was added as a new class; no existing class was edited and the existing metric tests are unchanged.
- **Invalid state is blocked or visible.** An invalid `SupportTicket` cannot be constructed, and bad CSV rows are returned explicitly as `RejectedRow(line_number, reason)` instead of being dropped or printed.

Class vs instance state
- Class level (shared, immutable): `SupportTicket.FINAL_STATUSES` (frozenset), `TicketValidator.REQUIRED_FIELDS` (tuple), `SlaBreachRate.DEFAULT_SLA_HOURS` (never mutated; each instance copies it).
- Instance level (per object): `CsvTicketLoader._path`, `SlaBreachRate._sla`, `PipelineResult.tickets` (`default_factory`, never a shared list).

## Data contracts and compatibility (schema note, v2)
The model keeps the **Day 01 fields** as its core (`ticket_id, category, priority, description, status, resolution_time_hours, customer_rating`) and adds the **Day 02 fields** as optional extras (`customer, subject, created_at, resolved_at`). Which columns a *file* must have is decided by a `TicketSchema`:

| Schema | Required columns | Chosen when |
|---|---|---|
| `day01` | ticket_id, category, priority, description, status | header has no `created_at` |
| `day02` | ticket_id, customer, subject, category, priority, status, created_at | header has `created_at` |

`main.py` auto-detects the schema (override with `--schema`). Day 01 metrics (priority counts, per-category resolution averages, rating average, unresolved count) are preserved as separate metric classes; `SlaBreachRate` is purely additive. `resolution_hours` uses `resolution_time_hours` when present, otherwise `resolved_at - created_at`.

## Malformed CSV policy
- Header names are trimmed and lower-cased. An **empty or duplicate** name (e.g. `status` and ` status`) stops the run with `MalformedCsvError` (CLI: message + exit code 1), so one column can never silently overwrite another.
- A record with **more or fewer fields than the header** is rejected with its line number and processing continues with later rows. Fields are never mapped by position past the header.
- Blank lines are skipped; a UTF-8 BOM is ignored.
- Missing *values* are handled per schema: required columns must be non-empty, optional ones may be blank.

## Assumptions
- Dates are `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`; priorities are low/medium/high/urgent; statuses are open/in_progress/resolved/closed; `customer_rating` is an integer 1-5; `resolution_time_hours` is a number >= 0.
- `resolved`/`closed` tickets need `resolved_at` or `resolution_time_hours`; open ones must not have `resolved_at`.
- "Unresolved" means status is not resolved/closed.
- `data/day01_tickets.csv` is a representative 7-column sample (including deliberately bad rows) used for regression tests. Replace it with the original approved Day 01 file and re-run to confirm identical results.
- Spaces/hyphens in status are normalised to `_` ("in progress" -> `in_progress`).

## Limitations
- The whole file is processed in one run; no streaming/progress or duplicate `ticket_id` detection.
- Dates are timezone-naive.
- SLA hours are illustrative defaults; custom SLA configs must list all four priorities (validated at construction).
- Only CSV is supported (but any `RowSource` can be plugged in).

## Actual output
See `docs/test_output.txt` (54 passed), `docs/main_output.txt` (Day 02 run), `docs/main_output_day01.txt` (Day 01 run), `docs/defect_repro_output.txt` (the reviewed malformed-CSV cases) and `docs/mutable_class_attr_demo_output.txt`.
