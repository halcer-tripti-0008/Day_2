# Support Ticket Processor (Day 02 refactor)

Small reusable components that load, clean, validate and analyse support tickets from a CSV.

## Setup
```bash
python3 -m pip install pytest      # only dependency (Python 3.10+)
python3 main.py                    # runs on data/tickets.csv
python3 main.py path/to/file.csv   # or your own file
python3 -m pytest -v               # 21 tests
```

## Structure and why responsibilities are separated
| Module | One responsibility | Knows nothing about |
|---|---|---|
| `models.py` | What a valid `SupportTicket` is (frozen dataclass, validates in `__post_init__`) | files, CSV, analytics |
| `loader.py` | CSV file -> raw dict rows | cleaning, rules |
| `cleaning.py` | Normalise text (trim, case) | rejecting rows |
| `validation.py` | Raw row -> `SupportTicket` or a list of every error | file formats |
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

## Assumptions
- Dates are `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`; priorities are low/medium/high/urgent; statuses are open/in_progress/resolved/closed.
- `resolved`/`closed` tickets must have `resolved_at`; open ones must not.
- Spaces/hyphens in status are normalised to `_` ("in progress" -> `in_progress`).

## Limitations
- The whole file is processed in one run; no streaming/progress or duplicate `ticket_id` detection.
- Dates are timezone-naive.
- SLA hours are illustrative defaults.
- Only CSV is supported (but any `RowSource` can be plugged in).

## Actual output
See `docs/test_output.txt` (21 passed), `docs/main_output.txt` (sample run: 6 valid, 5 rejected with reasons) and `docs/mutable_class_attr_demo_output.txt`.
