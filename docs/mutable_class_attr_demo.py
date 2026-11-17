"""Study demo: what goes wrong with mutable class attributes (viva Q2)."""


class BadTicketList:
    tickets = []                 # ONE list, stored on the class, shared by every instance

    def add(self, t):
        self.tickets.append(t)   # mutates the shared list, not a per-instance one


class GoodTicketList:
    def __init__(self):
        self.tickets = []        # a fresh list per instance

    def add(self, t):
        self.tickets.append(t)


a, b = BadTicketList(), BadTicketList()
a.add("T1")
print("BAD : b sees a's ticket ->", b.tickets, "| same object:", a.tickets is b.tickets)

c, d = GoodTicketList(), GoodTicketList()
c.add("T1")
print("GOOD: d is untouched    ->", d.tickets, "| same object:", c.tickets is d.tickets)
