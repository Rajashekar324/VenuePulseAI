import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app import app
from models import db


def build_and_train_pricing_model():
    print("1. Connecting to SQLite and extracting Event + Booking data...")
    with app.app_context():
        raw_sql = """
            SELECT
                b.id AS booking_id,
                b.event_id,
                b.timestamp AS purchase_date,
                b.total_amount,
                e.event_type,
                e.date AS event_date,
                e.capacity,
                e.base_ticket_price,
                e.total_budget
            FROM bookings b
            JOIN events e ON e.id = b.event_id
        """
        df = pd.read_sql(raw_sql, db.engine)

    if df.empty:
        raise RuntimeError("No booking data found. Seed the database before training.")

    print(f"Loaded {len(df)} booking rows.")

    print("2. Engineering features (days_until_event, current_tickets_sold, encoded event_type, current_sales_velocity)...")
    df["event_date"] = pd.to_datetime(df["event_date"], utc=True)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"], utc=True)

    df = df.sort_values(["event_id", "purchase_date"])

    df["tickets_in_booking"] = (df["total_amount"] / df["base_ticket_price"]).round().astype(int)
    df["tickets_in_booking"] = df["tickets_in_booking"].clip(lower=1)

    df["current_tickets_sold"] = df.groupby("event_id")["tickets_in_booking"].cumsum()

    df["days_until_event"] = (df["event_date"] - df["purchase_date"]).dt.days.clip(lower=0)

    # Event creation timestamp is not available in schema; use first observed booking as lifecycle start.
    df["first_observed_booking_date"] = df.groupby("event_id")["purchase_date"].transform("min")
    df["days_since_event_creation"] = (
        (df["purchase_date"] - df["first_observed_booking_date"]).dt.total_seconds() / 86400.0
    ).clip(lower=1.0)

    df["current_sales_velocity"] = df["current_tickets_sold"] / df["days_since_event_creation"]

    print("3. Building target variables...")
    final_attendance_map = df.groupby("event_id")["tickets_in_booking"].sum()
    df["expected_total_attendance"] = df["event_id"].map(final_attendance_map).astype(float)

    capacity_pct = (df["current_tickets_sold"] / df["capacity"]).clip(lower=0.0, upper=1.2)
    velocity_cap = max(float(df["current_sales_velocity"].quantile(0.95)), 1.0)
    velocity_score = (df["current_sales_velocity"] / velocity_cap).clip(lower=0.0, upper=2.0)
    urgency_score = np.where(
        df["days_until_event"] <= 7,
        0.22,
        np.where(df["days_until_event"] <= 30, 0.10, -0.05),
    )

    df["optimal_ticket_price"] = df["base_ticket_price"] * (
        1.0 + 0.28 * capacity_pct + 0.24 * velocity_score + urgency_score
    )
    df["optimal_ticket_price"] = np.clip(
        df["optimal_ticket_price"],
        df["base_ticket_price"] * 0.70,
        df["base_ticket_price"] * 2.30,
    )

    print("4. Training multi-output model with pandas + scikit-learn...")
    feature_columns = [
        "event_type",
        "days_until_event",
        "current_tickets_sold",
        "current_sales_velocity",
        "capacity",
        "base_ticket_price",
        "total_budget",
    ]

    X = df[feature_columns].copy()
    y = df[["expected_total_attendance", "optimal_ticket_price"]].copy()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    numeric_features = [
        "days_until_event",
        "current_tickets_sold",
        "current_sales_velocity",
        "capacity",
        "base_ticket_price",
        "total_budget",
    ]
    categorical_features = ["event_type"]

    event_type_encoder = OneHotEncoder(handle_unknown="ignore")
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", event_type_encoder, categorical_features),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", RandomForestRegressor(n_estimators=220, max_depth=14, random_state=42, n_jobs=-1)),
        ]
    )

    model.fit(X_train, y_train)

    print("5. Evaluating model outputs...")
    y_pred = model.predict(X_test)
    y_pred_df = pd.DataFrame(y_pred, columns=["expected_total_attendance", "optimal_ticket_price"])

    attendance_mae = mean_absolute_error(y_test["expected_total_attendance"], y_pred_df["expected_total_attendance"])
    price_mae = mean_absolute_error(y_test["optimal_ticket_price"], y_pred_df["optimal_ticket_price"])
    attendance_r2 = r2_score(y_test["expected_total_attendance"], y_pred_df["expected_total_attendance"])
    price_r2 = r2_score(y_test["optimal_ticket_price"], y_pred_df["optimal_ticket_price"])

    print(f"Attendance MAE: {attendance_mae:.2f}")
    print(f"Attendance R2: {attendance_r2:.4f}")
    print(f"Optimal Price MAE: {price_mae:.2f}")
    print(f"Optimal Price R2: {price_r2:.4f}")

    print("6. Saving model and encoders to ml_models/...")
    model_dir = "ml_models"
    os.makedirs(model_dir, exist_ok=True)

    model_path = os.path.join(model_dir, "demand_pricing_multi_output_model.pkl")
    encoder_path = os.path.join(model_dir, "event_type_encoder.pkl")
    metadata_path = os.path.join(model_dir, "demand_pricing_metadata.json")

    joblib.dump(model, model_path)

    standalone_encoder = OneHotEncoder(handle_unknown="ignore")
    standalone_encoder.fit(df[["event_type"]])
    joblib.dump(standalone_encoder, encoder_path)

    metadata = {
        "features": feature_columns,
        "targets": ["expected_total_attendance", "optimal_ticket_price"],
        "rows": int(len(df)),
        "metrics": {
            "attendance_mae": float(attendance_mae),
            "attendance_r2": float(attendance_r2),
            "optimal_price_mae": float(price_mae),
            "optimal_price_r2": float(price_r2),
        },
    }
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)

    print(f"Saved model: {model_path}")
    print(f"Saved encoder: {encoder_path}")
    print(f"Saved metadata: {metadata_path}")


if __name__ == "__main__":
    build_and_train_pricing_model()
