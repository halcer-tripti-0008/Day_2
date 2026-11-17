import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from tickets import (AnalyticsReport, AverageResolutionHours, CountByPriority, CountByStatus,
                     CsvTicketLoader, SlaBreachRate, TicketCleaner, TicketPipeline, TicketValidator)

path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "data" / "tickets.csv"
result = TicketPipeline(CsvTicketLoader(path), TicketCleaner(), TicketValidator()).run()

print(f"Loaded {len(result.tickets)} valid tickets, rejected {len(result.rejected)}")
for r in result.rejected:
    print(f"  line {r.line_number}: {r.reason}")

report = AnalyticsReport([CountByStatus(), CountByPriority(), AverageResolutionHours(), SlaBreachRate()])
print(json.dumps(report.run(result.tickets), indent=2))
