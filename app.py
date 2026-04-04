"""VenuePulseAI – Main Flask Application."""

import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# App & Database Initialization
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///venue.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# db is defined in models.py; bind it to this app
from models import db, Event, Ticket, ConcessionSale, StaffShift  # noqa: E402
db.init_app(app)


# ---------------------------------------------------------------------------
# Auto-create tables before the first request
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()


# ============================================================================
# ROUTES
# ============================================================================

# ---- Phase 1: Core Pages --------------------------------------------------

@app.route("/")
def index():
    """Patron homepage – upcoming events."""
    events = Event.query.filter(
        Event.date >= datetime.now(timezone.utc)
    ).order_by(Event.date.asc()).all()
    return render_template("index.html", events=events)


@app.route("/admin")
def admin_dashboard():
    """Admin dashboard – venue operations overview."""
    total_events = Event.query.count()
    total_tickets_sold = Ticket.query.filter_by(is_sold=True).count()
    total_concession_revenue = (
        db.session.query(db.func.coalesce(db.func.sum(ConcessionSale.price), 0))
        .scalar()
    )
    upcoming_events = Event.query.filter(
        Event.date >= datetime.now(timezone.utc)
    ).order_by(Event.date.asc()).limit(5).all()

    return render_template(
        "admin.html",
        total_events=total_events,
        total_tickets_sold=total_tickets_sold,
        total_concession_revenue=total_concession_revenue,
        upcoming_events=upcoming_events,
    )


# ---- Phase 2: Dynamic Pricing ML (placeholder) ----------------------------

@app.route("/api/predict-price/<int:event_id>", methods=["GET"])
def predict_price(event_id):
    """Placeholder – will return ML-predicted ticket price."""
    event = Event.query.get_or_404(event_id)
    return jsonify({
        "event_id": event.id,
        "event_name": event.name,
        "base_price": event.base_ticket_price,
        "predicted_price": event.base_ticket_price,  # stub
        "model_version": None,
        "message": "Phase 2 – ML pricing model not yet integrated.",
    })


# ---- Phase 3: GenAI Chatbot (placeholder) ---------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    """Placeholder – will handle GenAI chatbot queries."""
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "")
    return jsonify({
        "reply": (
            "I'm the VenuePulseAI assistant. "
            "This feature is coming in Phase 3!"
        ),
        "user_message": user_message,
        "model_version": None,
        "message": "Phase 3 – GenAI chatbot not yet integrated.",
    })


# ---- Phase 4: CrewAI Workflow (placeholder) --------------------------------

@app.route("/admin/run-agents", methods=["POST"])
def run_agents():
    """Placeholder – will trigger CrewAI multi-agent workflow."""
    return jsonify({
        "status": "pending",
        "agents_triggered": [],
        "message": "Phase 4 – CrewAI agent workflow not yet integrated.",
    })


# ---- Utility ---------------------------------------------------------------

@app.route("/health")
def health():
    """Quick health-check endpoint."""
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=8080)
