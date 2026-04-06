"""Export analytics datasets for Power BI dashboard embedding."""

from pathlib import Path

import pandas as pd

from app import app
from models import Booking, Event, HelpdeskTicket, StaffShift, Ticket, db


EXPORT_DIR = Path(__file__).resolve().parent / "powerbi_exports"


def build_dashboard_a_rows() -> list[dict]:
    """Build rows for revenue and demand heatmap export."""
    booking_counts_sq = (
        db.session.query(
            Booking.event_id.label("event_id"),
            db.func.count(Booking.id).label("booking_count"),
        )
        .group_by(Booking.event_id)
        .subquery()
    )

    sold_tickets_sq = (
        db.session.query(
            Ticket.event_id.label("event_id"),
            db.func.count(Ticket.id).label("tickets_sold"),
        )
        .filter(Ticket.is_sold.is_(True))
        .group_by(Ticket.event_id)
        .subquery()
    )

    event_metrics = (
        db.session.query(
            Event.name.label("event_name"),
            Event.base_ticket_price,
            Event.capacity,
            db.func.coalesce(booking_counts_sq.c.booking_count, 0).label("booking_count"),
            db.func.coalesce(sold_tickets_sq.c.tickets_sold, 0).label("tickets_sold"),
        )
        .outerjoin(booking_counts_sq, booking_counts_sq.c.event_id == Event.id)
        .outerjoin(sold_tickets_sq, sold_tickets_sq.c.event_id == Event.id)
        .order_by(Event.date.asc())
        .all()
    )

    rows = []
    for metric in event_metrics:
        capacity = int(metric.capacity or 0)
        base_price = float(metric.base_ticket_price or 0)
        booking_count = int(metric.booking_count or 0)
        tickets_sold = int(metric.tickets_sold or 0)

        ticket_velocity = tickets_sold if tickets_sold > 0 else booking_count
        demand_ratio = (ticket_velocity / capacity) if capacity > 0 else 0.0

        if demand_ratio >= 0.75:
            demand_status = "Surge"
            multiplier = 1.20
        elif demand_ratio >= 0.35:
            demand_status = "Medium"
            multiplier = 1.05
        else:
            demand_status = "Cold"
            multiplier = 0.90

        ai_suggested_price = round(base_price * multiplier, 2) if base_price > 0 else 0.0

        rows.append(
            {
                "event_name": metric.event_name,
                "demand_status": demand_status,
                "ai_suggested_price": ai_suggested_price,
                "ticket_velocity": ticket_velocity,
            }
        )

    return rows


def build_dashboard_b_rows() -> list[dict]:
    """Build one-row helpdesk operations summary."""
    total_tickets = HelpdeskTicket.query.count()

    ai_resolved_simple = HelpdeskTicket.query.filter(
        db.func.lower(HelpdeskTicket.status).in_(
            ["closed", "closed_by_ai", "ai_closed", "resolved_by_ai"]
        )
    ).count()

    human_escalated_complex = HelpdeskTicket.query.filter(
        (db.func.lower(HelpdeskTicket.status).in_(
            [
                "open",
                "pending",
                "pending_human",
                "assigned_to_human",
                "escalated",
                "escalated_to_human",
            ]
        ))
        | (db.func.lower(HelpdeskTicket.status).like("%human%"))
    ).count()

    return [
        {
            "total_tickets": int(total_tickets or 0),
            "ai_resolved_simple": int(ai_resolved_simple or 0),
            "human_escalated_complex": int(human_escalated_complex or 0),
        }
    ]


def build_dashboard_c_rows() -> list[dict]:
    """Build rows for operational efficiency and staffing export."""
    staff_counts_sq = (
        db.session.query(
            StaffShift.event_id.label("event_id"),
            db.func.count(StaffShift.id).label("staff_count"),
        )
        .group_by(StaffShift.event_id)
        .subquery()
    )

    event_metrics = (
        db.session.query(
            Event.name.label("event_name"),
            Event.total_budget,
            Event.capacity,
            db.func.coalesce(staff_counts_sq.c.staff_count, 0).label("staff_count"),
        )
        .outerjoin(staff_counts_sq, staff_counts_sq.c.event_id == Event.id)
        .order_by(Event.date.asc())
        .all()
    )

    rows = []
    for metric in event_metrics:
        total_budget = float(metric.total_budget or 0)
        rows.append(
            {
                "event_name": metric.event_name,
                "total_budget": total_budget,
                "staffing_cost": total_budget,
                "expected_capacity": int(metric.capacity or 0),
                "allocated_staff_count": int(metric.staff_count or 0),
            }
        )

    return rows


def export_dashboards() -> None:
    """Export all dashboard datasets to CSV files for Power BI ingestion."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    dashboard_a_df = pd.DataFrame(
        build_dashboard_a_rows(),
        columns=[
            "event_name",
            "demand_status",
            "ai_suggested_price",
            "ticket_velocity",
        ],
    ).fillna(0)

    dashboard_b_df = pd.DataFrame(
        build_dashboard_b_rows(),
        columns=[
            "total_tickets",
            "ai_resolved_simple",
            "human_escalated_complex",
        ],
    ).fillna(0)

    dashboard_c_df = pd.DataFrame(
        build_dashboard_c_rows(),
        columns=[
            "event_name",
            "total_budget",
            "staffing_cost",
            "expected_capacity",
            "allocated_staff_count",
        ],
    ).fillna(0)

    dashboard_a_path = EXPORT_DIR / "dashboard_a_heatmap.csv"
    dashboard_b_path = EXPORT_DIR / "dashboard_b_ops.csv"
    dashboard_c_path = EXPORT_DIR / "dashboard_c_staffing.csv"

    dashboard_a_df.to_csv(dashboard_a_path, index=False)
    dashboard_b_df.to_csv(dashboard_b_path, index=False)
    dashboard_c_df.to_csv(dashboard_c_path, index=False)

    print(f"Export complete. CSV files written to: {EXPORT_DIR}")


if __name__ == "__main__":
    with app.app_context():
        export_dashboards()
