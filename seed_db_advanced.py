import random
from datetime import datetime, timedelta
from collections import defaultdict

import faker
from werkzeug.security import generate_password_hash

from app import app
from models import db, User, Event, Booking, Ticket, HelpdeskTicket


def interpolate_datetime(start_dt, end_dt, fraction):
    """Return a datetime between start and end using a 0..1 fraction."""
    fraction = max(0.0, min(1.0, fraction))
    duration_seconds = (end_dt - start_dt).total_seconds()
    return start_dt + timedelta(seconds=duration_seconds * fraction)


def random_datetime_between(start_dt, end_dt):
    """Return a random datetime between start and end."""
    if end_dt <= start_dt:
        return start_dt
    return interpolate_datetime(start_dt, end_dt, random.random())


def generate_mock_data():
    fake = faker.Faker()

    with app.app_context():
        print("Clearing existing database tables...")
        db.drop_all()
        db.create_all()

        print("Generating 50 Users (Admins and Patrons)...")
        users = []

        primary_admin = User(name="Administrator", email="admin@venuepulse.com", role="admin")
        primary_admin.password_hash = generate_password_hash("admin123")
        db.session.add(primary_admin)
        users.append(primary_admin)

        primary_user = User(name="Standard User", email="user@venuepulse.com", role="user")
        primary_user.password_hash = generate_password_hash("user123")
        db.session.add(primary_user)
        users.append(primary_user)

        for _ in range(48):
            role = random.choices(["user", "admin"], weights=[90, 10])[0]
            user = User(name=fake.name(), email=fake.unique.email(), role=role)
            user.password_hash = generate_password_hash("password123")
            db.session.add(user)
            users.append(user)

        db.session.commit()

        print("Generating 200 Events (Past & Future)...")
        events = []
        event_categories = ["Concert", "Conference", "Sports", "Comedy"]
        event_demand_status = {}
        demand_counts = defaultdict(int)

        budget_multipliers = {
            "Concert": 1.30,
            "Conference": 1.15,
            "Sports": 1.55,
            "Comedy": 0.85,
        }
        fixed_overheads = {
            "Concert": 45000.0,
            "Conference": 30000.0,
            "Sports": 70000.0,
            "Comedy": 12000.0,
        }

        for _ in range(200):
            event_type = random.choice(event_categories)

            if event_type == "Concert":
                name = f"{fake.company()} Tour"
                genre = random.choice(["Rock", "Pop", "EDM", "Hip-Hop", "Classical"])
                base_price = random.uniform(40.0, 250.0)
            elif event_type == "Conference":
                name = f"{fake.catch_phrase()} Summit"
                genre = "Technology & Business"
                base_price = random.uniform(150.0, 900.0)
            elif event_type == "Comedy":
                name = f"{fake.name()} Live Special"
                genre = "Stand-up"
                base_price = random.uniform(20.0, 80.0)
            else:
                name = f"{fake.city()} vs {fake.city()} Championship"
                genre = "Athletics"
                base_price = random.uniform(50.0, 300.0)

            days_offset = random.randint(-180, 180)
            capacity = random.choice([500, 1500, 5000, 15000, 50000])

            # Realistic budget model: larger venues and premium event types cost more.
            scale_factor = 1.0 + (capacity / 50000.0) * 1.8
            ticket_economics = (
                capacity
                * base_price
                * budget_multipliers[event_type]
                * random.uniform(0.22, 0.45)
            )
            total_budget = (ticket_economics + fixed_overheads[event_type]) * scale_factor

            if 0 <= days_offset <= 21:
                demand_status = random.choices(
                    ["Cold", "On Track", "Surge Potential"],
                    weights=[55, 30, 15],
                    k=1,
                )[0]
            else:
                demand_status = random.choices(
                    ["Cold", "On Track", "Surge Potential"],
                    weights=[20, 45, 35],
                    k=1,
                )[0]

            event = Event(
                name=name,
                genre=genre,
                event_type=event_type,
                date=datetime.now() + timedelta(days=days_offset),
                capacity=capacity,
                base_ticket_price=base_price,
                total_budget=total_budget,
            )
            db.session.add(event)
            db.session.flush()

            events.append(event)
            event_demand_status[event.id] = demand_status
            demand_counts[demand_status] += 1

        db.session.commit()

        print("Simulating bookings with explicit demand statuses...")
        total_bookings = 0
        total_tickets = 0
        now = datetime.now()

        for event in events:
            demand_status = event_demand_status.get(event.id, "On Track")

            lifecycle_start = min(
                now - timedelta(days=random.randint(20, 90)),
                event.date - timedelta(days=45),
            )
            lifecycle_end = min(event.date, now)
            if lifecycle_end <= lifecycle_start:
                lifecycle_start = lifecycle_end - timedelta(days=7)

            base_scale = max(8, min(90, event.capacity // 450))

            if demand_status == "Cold":
                # Very few bookings, mostly close to event date.
                if 0 <= (event.date - now).days <= 30:
                    transactions_to_simulate = random.randint(2, 8)
                else:
                    transactions_to_simulate = random.randint(3, 12)
                near_event_start = max(lifecycle_start, event.date - timedelta(days=10))
                qty_min, qty_max = 1, 2

                def booking_timestamp(_index):
                    return random_datetime_between(near_event_start, lifecycle_end)

            elif demand_status == "On Track":
                # Steady linear bookings across the lifecycle.
                transactions_to_simulate = random.randint(max(10, base_scale // 2), max(18, base_scale + 8))
                qty_min, qty_max = 1, 3

                def booking_timestamp(index):
                    fraction = (index + random.uniform(0.1, 0.9)) / max(1, transactions_to_simulate)
                    return interpolate_datetime(lifecycle_start, lifecycle_end, fraction)

            else:
                # Early booking spike soon after event creation.
                transactions_to_simulate = random.randint(max(24, base_scale), max(40, base_scale + 25))
                early_spike_end = interpolate_datetime(lifecycle_start, lifecycle_end, 0.15)
                qty_min, qty_max = 1, 4

                def booking_timestamp(_index):
                    if random.random() < 0.78:
                        return random_datetime_between(lifecycle_start, early_spike_end)
                    return random_datetime_between(early_spike_end, lifecycle_end)

            for i in range(transactions_to_simulate):
                buyer = random.choice(users)
                buy_date = booking_timestamp(i)

                if buy_date > now:
                    buy_date = now - timedelta(hours=random.randint(1, 48))

                qty = random.randint(qty_min, qty_max)

                booking = Booking(
                    user_id=buyer.id,
                    event_id=event.id,
                    total_amount=event.base_ticket_price * qty,
                    payment_status="completed",
                    timestamp=buy_date,
                )
                db.session.add(booking)
                db.session.flush()

                for _ in range(qty):
                    ticket = Ticket(
                        event_id=event.id,
                        booking_id=booking.id,
                        current_price=event.base_ticket_price,
                        is_sold=True,
                    )
                    db.session.add(ticket)
                    total_tickets += 1

                total_bookings += 1

        db.session.commit()

        print("Demand pattern distribution:")
        print(f"  Cold: {demand_counts['Cold']} events")
        print(f"  On Track: {demand_counts['On Track']} events")
        print(f"  Surge Potential: {demand_counts['Surge Potential']} events")

        print("Generating random Helpdesk queries...")
        for _ in range(15):
            helpdesk_user = random.choice(users)
            status = random.choice(["open", "closed"])
            ticket = HelpdeskTicket(
                user_id=helpdesk_user.id,
                subject=random.choice([
                    "Refund requested",
                    "Cant find my ticket",
                    "Wrong seat mapping",
                    "Payment failed",
                ]),
                description=fake.text(),
                status=status,
                created_at=now - timedelta(days=random.randint(1, 30)),
            )
            db.session.add(ticket)

        db.session.commit()

        print("\n=== SYSTEM SEED SUCCESS ===")
        print("Generated 50 Users")
        print("Generated 200 Events")
        print(f"Generated {total_bookings} Bookings comprising {total_tickets} Tickets")
        print("Use pip install faker to execute script if missing dependencies.")


if __name__ == "__main__":
    generate_mock_data()
