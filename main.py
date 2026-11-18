"""Run the ticket pipeline on a CSV.

Usage:
    python3 main.py [path.csv] [--schema auto|day01|day02]

Exit codes: 0 ok, 1 unreadable/malformed file or wrong columns, 2 bad arguments.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from tickets import (SCHEMAS, AnalyticsReport, AverageCustomerRating, AverageResolutionByCategory,
                     AverageResolutionHours, CountByPriority, CountByStatus, CsvTicketLoader,
                     MalformedCsvError, SlaBreachRate, TicketCleaner, TicketPipeline,
                     TicketValidator, UnresolvedCount, detect_schema)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", default=Path(__file__).parent / "data" / "tickets.csv")
    parser.add_argument("--schema", choices=["auto", *SCHEMAS], default="auto")
    args = parser.parse_args(argv)

    loader = CsvTicketLoader(args.path)
    try:
        header = loader.header()
        schema = detect_schema(header) if args.schema == "auto" else SCHEMAS[args.schema]
        missing = schema.missing_columns(header)
        if missing:
            print(f"ERROR: file is missing required column(s) for schema '{schema.name}': "
                  f"{', '.join(missing)}", file=sys.stderr)
            return 1
        result = TicketPipeline(loader, TicketCleaner(), TicketValidator(schema)).run()
    except (MalformedCsvError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Schema: {schema.name}")
    print(f"Loaded {len(result.tickets)} valid tickets, rejected {len(result.rejected)}")
    for r in result.rejected:
        print(f"  line {r.line_number}: {r.reason}")

    report = AnalyticsReport([
        CountByStatus(), CountByPriority(), AverageResolutionHours(),
        AverageResolutionByCategory(), AverageCustomerRating(), UnresolvedCount(), SlaBreachRate(),
    ])
    print(json.dumps(report.run(result.tickets), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
