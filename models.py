"""Database models for VenuePulseAI – Live Event & Venue Management."""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------
class Event(db.Model):
    """A live event hosted at the venue."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    base_ticket_price = db.Column(db.Float, nullable=False)

    # Relationships
    tickets = db.relationship(
        "Ticket", backref="event", lazy=True, cascade="all, delete-orphan"
    )
    concession_sales = db.relationship(
        "ConcessionSale", backref="event", lazy=True, cascade="all, delete-orphan"
    )
    staff_shifts = db.relationship(
        "StaffShift", backref="event", lazy=True, cascade="all, delete-orphan"
    )

    def __init__(self, name, date, genre, capacity, base_ticket_price):
        self.name = name
        self.date = date
        self.genre = genre
        self.capacity = capacity
        self.base_ticket_price = base_ticket_price

    def __repr__(self):
        return (
            f"<Event id={self.id} name='{self.name}' "
            f"date={self.date:%Y-%m-%d} genre='{self.genre}' "
            f"capacity={self.capacity} base_price={self.base_ticket_price}>"
        )


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------
class Ticket(db.Model):
    """A ticket issued for a specific event."""

    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id"), nullable=False
    )
    current_price = db.Column(db.Float, nullable=False)
    is_sold = db.Column(db.Boolean, default=False, nullable=False)
    patron_name = db.Column(db.String(150), nullable=True)

    def __init__(self, event_id, current_price, is_sold=False, patron_name=None):
        self.event_id = event_id
        self.current_price = current_price
        self.is_sold = is_sold
        self.patron_name = patron_name

    def __repr__(self):
        status = "SOLD" if self.is_sold else "AVAILABLE"
        return (
            f"<Ticket id={self.id} event_id={self.event_id} "
            f"price={self.current_price} status={status} "
            f"patron='{self.patron_name}'>"
        )


# ---------------------------------------------------------------------------
# ConcessionSale
# ---------------------------------------------------------------------------
class ConcessionSale(db.Model):
    """A food / beverage / merchandise sale at an event."""

    __tablename__ = "concession_sales"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id"), nullable=False
    )
    item_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __init__(self, event_id, item_name, price, timestamp=None):
        self.event_id = event_id
        self.item_name = item_name
        self.price = price
        if timestamp is not None:
            self.timestamp = timestamp

    def __repr__(self):
        return (
            f"<ConcessionSale id={self.id} event_id={self.event_id} "
            f"item='{self.item_name}' price={self.price} "
            f"at={self.timestamp}>"
        )


# ---------------------------------------------------------------------------
# StaffShift
# ---------------------------------------------------------------------------
class StaffShift(db.Model):
    """A staff member's shift assignment for an event."""

    __tablename__ = "staff_shifts"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id"), nullable=False
    )
    role = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    def __init__(self, event_id, role, start_time, end_time):
        self.event_id = event_id
        self.role = role
        self.start_time = start_time
        self.end_time = end_time

    def __repr__(self):
        return (
            f"<StaffShift id={self.id} event_id={self.event_id} "
            f"role='{self.role}' "
            f"from={self.start_time:%H:%M} to={self.end_time:%H:%M}>"
        )
