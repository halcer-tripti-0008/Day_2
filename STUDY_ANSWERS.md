# Day 02 — Answers: Object-Oriented Python & Reusable Modules

Everything below is backed by the code in this repo (`src/tickets`, `tests/`, `docs/`).
Read it, run it, and re-explain it in your own words before submitting (training rule).

---
## Part 1 — Study required outputs

### 1.1 Classes and object model — small classes + instance state
```python
class Counter:
    step = 1                      # CLASS attribute: one copy, shared

    def __init__(self, start=0):  # constructor: runs when an object is created
        self.value = start        # INSTANCE attribute: one per object, lives in self.__dict__

    def increment(self):
        self.value += self.step   # `self` = the specific object the method was called on

a, b = Counter(), Counter(10)
a.increment()
print(a.value, b.value)           # 1 10 -> instances have independent state
```
- **Instance state** = the data stored on `self` (`a.value`). Each object has its own, so changing `a` never affects `b`.
- **Lifecycle:** `Counter()` -> `__new__` creates the object -> `__init__` sets its state -> used -> garbage-collected when no references remain.
- **In the project:** `CsvTicketLoader._path` and `SlaBreachRate._sla` are instance state; `SupportTicket.FINAL_STATUSES` is class state (shared, immutable).

### 1.2 OOP design — compare two designs and justify one
Problem: support several analytics (count by status, average resolution, SLA breach rate).

| | Design A: inheritance | Design B: composition + interface (chosen) |
|---|---|---|
| Shape | `BaseAnalytics` -> `StatusAnalytics`, `ResolutionAnalytics`, ... each overrides `run()` | Small `Metric` classes with `compute()`; `AnalyticsReport` holds a list of them |
| Combining metrics | Need multiple inheritance or a new subclass per combination | Just put the metrics in the list |
| Coupling | Subclasses depend on the base class internals (fragile base class) | Report depends only on the `compute()` contract |
| Testing | Must build the subclass hierarchy | Test each metric alone with plain tickets |
| Adding a metric | New subclass, risk of changing base | New class; nothing else edited |

**Justification:** The metrics are not specialisations of one "thing" (no genuine *is-a* relationship); they are interchangeable behaviours. Composition lowers coupling and makes extension safe, so Design B is used in `analytics.py`.

Other OOP concepts, as used here
- **Encapsulation:** `_path`, `_sla`, `_metrics` are private by convention; callers use `compute()` / `rows()`.
- **Polymorphism:** `AnalyticsReport` calls `m.compute(...)` on any `Metric` without caring which one it is.
- **Abstract interface:** `typing.Protocol` (`Metric`, `RowSource`) describes the contract without forcing inheritance.
- **Inheritance:** deliberately unused, because there was no reason for it.

### 1.3 Python data model — readable, predictable objects
- `@dataclass` auto-generates `__init__`, `__repr__` and `__eq__`, so `SupportTicket(...)` prints readably and two equal tickets compare equal.
- `frozen=True` makes instances immutable (and hashable), so no one can corrupt a ticket after creation.
- `@property` (`is_final`, `resolution_hours`) gives computed values with attribute syntax and no stored duplicate that can go stale.
- `__repr__` is for developers (unambiguous, ideally `eval`-able); `__str__` is for users (readable). If you define only one, define `__repr__`.
- Class vs instance attribute: `FINAL_STATUSES` is on the class; fields are on each instance.

### 1.4 Design review — the deliberately messy class (`docs/messy_class_review.py`)
| # | Issue | Principle broken | Fix (what the refactor did) |
|---|---|---|---|
| 1 | `all_tickets = []` at class level | Mutable class attribute: shared by all instances | Per-instance state / `default_factory` (`PipelineResult`) |
| 2 | Opens a file in `__init__`, never closes | Resource leak, hidden side effect | `with` block inside `CsvTicketLoader.rows()` |
| 3 | `load()` loads, cleans, validates, stores | Single responsibility, low cohesion | Split into loader / cleaner / validator / pipeline |
| 4 | Allowed priorities hard-coded, `urgent` missing | Rules scattered, easy to drift | `Priority` enum is the single source of truth |
| 5 | `print("bad row")` | Errors can't be handled by callers | `TicketValidationError` + `RejectedRow(line, reason)` |
| 6 | Stores raw dicts | Invalid state possible, stringly-typed | `SupportTicket` frozen dataclass validated at construction |
| 7 | Analytics inside the loading class | Tight coupling, untestable without a CSV | `Metric` classes that take tickets |
| 8 | `/ len(...)` with no data | Unhandled edge case (`ZeroDivisionError`) | Metrics return `None` when there is no data |
| 9 | Sends email inside the class | Mixed concerns; hard-wired external dependency | Reporting/notification would be its own injected component |

It is a classic **god object**: it knows about files, rules, state, maths and email.

---
## Part 2 — Implementation (Tasks A–D)

| Task | Where | Result |
|---|---|---|
| A — Model domain | `src/tickets/models.py` | `SupportTicket` frozen dataclass; required fields; all cross-field rules (`resolved` needs `resolved_at`, no time travel) enforced in `__post_init__` |
| B — Separate responsibilities | `loader.py`, `cleaning.py`, `validation.py`, `analytics.py`, `pipeline.py` | One responsibility per module; no inheritance; dependencies injected |
| C — Extend behaviour | `analytics.py` -> `SlaBreachRate` | New metric as a new class; existing classes and their tests untouched |
| D — Test + document | `tests/test_tickets.py`, `README.md`, git commit | 21 tests pass; README explains the design; committed |

### Actual test output (`python3 -m pytest -v`)
```
collected 21 items
... 21 PASSED ...
============================== 21 passed in 0.04s ==============================
```
(full log: `docs/test_output.txt`)

### Actual sample run (`python3 main.py` on `data/tickets.csv`)
```
Loaded 6 valid tickets, rejected 5
  line 8: missing customer
  line 9: invalid priority 'critical' (allowed: low, medium, high, urgent)
  line 10: invalid created_at '09/01/2025'
  line 11: resolved_at cannot be before created_at
  line 12: status 'resolved' requires resolved_at
{ "count_by_status": {"resolved": 3, "closed": 1, "open": 1, "in_progress": 1},
  "count_by_priority": {"high": 2, "medium": 2, "urgent": 1, "low": 1},
  "avg_resolution_hours": 40.38,
  "sla_breach_rate": 0.5 }
```
Hand check: resolved tickets took 11, 48, 6.5, 96 hours -> mean 40.375 -> 40.38. SLA: urgent 6.5h > 4h breaches and medium 96h > 72h breaches, so 2 of 4 = 0.5.

---
## Part 3 — Acceptance criteria
- [x] Each component has one clear responsibility (table in README)
- [x] Class vs instance state used correctly (immutable shared constants; per-instance config; `default_factory`)
- [x] Invalid object state is prevented (`SupportTicket.__post_init__`) or explicitly represented (`RejectedRow`)
- [x] Tests cover normal and invalid behaviour (valid/invalid model, validator errors, bad rows, missing file, empty data)
- [ ] Developer can explain why the design is maintainable -> that's you; use the viva answers below

---
## Part 4 — Technical viva (model answers)

**1. When is composition preferable to inheritance?**
When the relationship is *has-a* or *uses-a*, not a true *is-a*. Composition keeps coupling low (depend on a small interface, not a parent's internals), lets you swap behaviour at runtime or in tests, avoids deep hierarchies and the fragile-base-class problem, and combines behaviours freely (a list of metrics) where inheritance would need a subclass per combination. Use inheritance only for a real specialisation with shared behaviour that substitutes safely for the parent (Liskov).

**2. What can go wrong with mutable class attributes?**
A mutable object (list/dict/set) defined on the class is a single object shared by every instance, so `a.tickets.append(x)` mutates what `b` sees too (see `docs/mutable_class_attr_demo.py`: `b.tickets` shows `['T1']` after only `a` added it). It causes cross-instance leaks, hidden coupling and test-order-dependent bugs. Fix: create mutable state in `__init__` (or `field(default_factory=list)` in dataclasses); keep class attributes immutable (tuple, frozenset, constants). Note: a dataclass rejects a plain `[]` default for exactly this reason.

**3. What does encapsulation achieve in Python?**
It bundles data with the methods that operate on it and hides internals behind a stable interface, so internals can change without breaking callers and invariants are protected (e.g. `SupportTicket` can't be built or changed into an invalid state). Python has no true private members; it relies on convention (`_name`), name mangling (`__name`) and properties for controlled access. So it's about a clear contract and protecting invariants, not security.

**4. How do you avoid a god object?**
Give each class one reason to change (single responsibility); describe it in one sentence without "and". Separate I/O, validation, business rules and presentation; keep data models free of behaviour that needs external resources; inject dependencies instead of creating them inside; watch for warning signs (many unrelated methods, many imports, can't test without a file/network, class name like `Manager`/`Handler`/`Utils`). Here, the old `load()` became loader + cleaner + validator + pipeline + metrics.

**5. How would you test a class with an external dependency?**
Make the dependency injectable (constructor parameter typed by a small interface), then pass a fake/stub/mock in tests. `TicketPipeline` takes a `RowSource`, so tests use `FakeSource([...rows])` with no file system. For the real adapter (`CsvTicketLoader`) write a few thin integration tests with pytest's `tmp_path`. Test failure paths too (missing file). Use mocks (`unittest.mock`) for things you can't fake simply (HTTP, email), and avoid patching internals.

---
## Part 5 — Daily report (ready to submit; edit to match your actual experience)

- **Topics learned:** Instance vs class state; encapsulation, composition vs inheritance, polymorphism via `Protocol`; dataclasses (`frozen`, `__post_init__`, `default_factory`); properties; `__repr__`/`__str__`; single responsibility, cohesion/coupling, dependency injection; testing with fakes and `tmp_path`.
- **What I can explain without notes:** Why a mutable class attribute is shared across instances; why composition was chosen for analytics; how an invalid `SupportTicket` is prevented; how the pipeline can be tested without a real file.
- **Implementation completed:** `SupportTicket` model; `CsvTicketLoader`, `TicketCleaner`, `TicketValidator`, `TicketPipeline`; metrics (`CountByStatus`, `CountByPriority`, `AverageResolutionHours`) and new `SlaBreachRate`; `AnalyticsReport`; README; git commit.
- **Tests/experiment results:** 21 passed in 0.04 s. Sample CSV of 11 rows -> 6 valid, 5 rejected with exact reasons; avg resolution 40.38 h, SLA breach rate 0.5; mutable-attribute demo printed `BAD: ['T1']` vs `GOOD: []`.
- **One bug or challenge and its root cause:** *(replace with your own if different)* Designing the cross-field rule "resolved tickets need `resolved_at`". First instinct was to check it in the validator only, but then a `SupportTicket` built directly in code could still be invalid. Root cause: validation was in the wrong layer. Fix: keep the invariant in the model's `__post_init__`, and let the validator only handle raw-text-to-typed conversion.
- **One design decision and why:** Metrics are separate classes behind a `Metric` protocol, composed by `AnalyticsReport`, rather than an inheritance tree or one big analytics class. That let `SlaBreachRate` be added without editing existing code, and each metric is tested in isolation.
- **Blocker and what I tried:** None blocking. *(If you hit one, write the error, your hypothesis, and what you tried first.)*
- **Tomorrow's plan:** Day 03 — build on these components (e.g. pandas/NumPy for the same analytics, and compare against the pure-Python version).
