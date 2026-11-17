class Seats:
    def __init__(self, capacity):
        self.remaining = dict(capacity)

    def reserve(self, event, count):
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("invalid count")
        if self.remaining.get(event, 0) < count:
            raise ValueError("insufficient seats")
        self.remaining[event] -= count

    def release(self, event, count):
        self.remaining[event] += count
