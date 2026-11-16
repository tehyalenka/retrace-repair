from seats import Seats
from ledger import Ledger

class BookingService:
    def __init__(self, capacity):
        self.seats = Seats(capacity)
        self.ledger = Ledger()
        self.bookings = {}
        self.next_id = 1

    def book(self, event, customer, seats):
        self.seats.reserve(event, seats)
        booking_id = self.next_id
        self.next_id += 1
        self.bookings[booking_id] = (event, customer, seats)
        self.ledger.charge(booking_id, seats * 25)
        return booking_id

    def cancel(self, booking_id):
        booking = self.bookings.get(booking_id)
        if not booking:
            return False
        event, customer, seats = booking
        self.seats.release(event, seats)
        self.ledger.refund(booking_id, seats * 25)
        return True
