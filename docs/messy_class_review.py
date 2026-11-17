"""Study: a deliberately messy class (the 'before'). Review is in STUDY_ANSWERS.md."""
import csv

class TicketManager:
    all_tickets = []                      # (1) mutable class attribute -> shared by all instances
    db = None

    def __init__(self, path):
        self.path = path
        self.db = open("log.txt", "a")    # (2) opens a resource in __init__, never closed

    def load(self):                       # (3) loads, cleans, validates and stores in one method
        for row in csv.DictReader(open(self.path)):
            row["priority"] = row["priority"].strip().lower()
            if row["priority"] not in ["low", "medium", "high"]:   # (4) rules hard-coded, 'urgent' missing
                print("bad row", row)     # (5) print as error handling; caller can't react
                continue
            self.all_tickets.append(row)  # (6) raw dicts, not a model: invalid state possible

    def avg_hours(self):                  # (7) analytics welded to loading; can't test without a CSV
        return sum(float(t["hours"]) for t in self.all_tickets) / len(self.all_tickets)  # (8) ZeroDivisionError

    def send_report(self):                # (9) emailing inside the same class
        import smtplib
        smtplib.SMTP("localhost").sendmail("a", "b", str(self.avg_hours()))
