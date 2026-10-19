from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import database


FEATURE_NAMES = ("purchase_count", "median_interval", "days_since_last", "average_quantity")


def _groups(history):
    grouped = {}
    for row in history:
        grouped.setdefault(row["item_name"].casefold(), []).append(row)
    return grouped


def _features(group, anchor_date, latest_index):
    observed = group[: latest_index + 1]
    purchase_dates = [date.fromisoformat(row["purchase_date"]) for row in observed]
    intervals = np.diff([day.toordinal() for day in purchase_dates])
    median_interval = float(np.median(intervals)) if len(intervals) else 14.0
    return [
        float(len(observed)),
        max(median_interval, 1.0),
        float(max((anchor_date - purchase_dates[-1]).days, 0)),
        float(np.mean([row["quantity"] for row in observed])),
    ]


def _training_data(history):
    groups = _groups(history)
    features, labels = [], []
    for group in groups.values():
        dates = [date.fromisoformat(row["purchase_date"]) for row in group]
        if len(dates) < 2:
            continue
        for index in range(len(dates) - 1):
            anchor = dates[index]
            while anchor < dates[index + 1]:
                features.append(_features(group, anchor, index))
                labels.append(int((dates[index + 1] - anchor).days <= 7))
                anchor += timedelta(days=3)
    return np.asarray(features, dtype=float), np.asarray(labels, dtype=int)


def _signature(history):
    payload = [
        [row["id"], row["item_name"], row["purchase_date"], row["quantity"], row["unit_price"]]
        for row in history
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def train_classifier(history):
    features, labels = _training_data(history)
    if len(features) < 4 or len(np.unique(labels)) < 2:
        return None, {"samples": int(len(features)), "classes": int(len(np.unique(labels)))}
    model = make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    )
    model.fit(features, labels)
    return model, {"samples": int(len(features)), "classes": int(len(np.unique(labels)))}


def _load_or_train(history, model_path):
    signature = _signature(history)
    path = Path(model_path)
    if path.exists():
        try:
            artifact = joblib.load(path)
            if artifact.get("signature") == signature:
                return artifact.get("model")
        except (OSError, ValueError, EOFError, AttributeError):
            pass
    model, _ = train_classifier(history)
    return model


def _fallback_score(days_until):
    return 1 / (1 + math.exp(max(min((days_until - 4) / 2.5, 40), -40)))


def predict_items(database_path, model_path=None, limit=None, today=None):
    history = database.get_purchase_history(database_path)
    if not history:
        return []
    today = today or date.today()
    groups = _groups(history)
    model = _load_or_train(history, model_path) if model_path else train_classifier(history)[0]
    predictions = []
    for group in groups.values():
        group.sort(key=lambda row: (row["purchase_date"], row["id"]))
        dates = [date.fromisoformat(row["purchase_date"]) for row in group]
        intervals = np.diff([day.toordinal() for day in dates])
        median_interval = float(np.median(intervals)) if len(intervals) else 14.0
        median_interval = max(median_interval, 1.0)
        expected = dates[-1] + timedelta(days=round(median_interval))
        days_until = (expected - today).days
        current_features = np.asarray([_features(group, today, len(group) - 1)], dtype=float)
        model_score = float(model.predict_proba(current_features)[0][1]) if model else _fallback_score(days_until)
        urgency_score = _fallback_score(days_until)
        score = 0.75 * model_score + 0.25 * urgency_score if model else model_score
        if score >= 0.70 or (days_until <= 2 and score >= 0.52):
            priority = "HIGH"
        elif score >= 0.38:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        if days_until < 0:
            reason = f"Usually bought every {round(median_interval)} days; about {abs(days_until)} days overdue."
        elif days_until <= 3:
            reason = f"Usually bought every {round(median_interval)} days; due within {max(days_until, 0)} days."
        else:
            reason = f"Recent purchases suggest a {round(median_interval)}-day restock cycle."
        predictions.append(
            {
                "item_name": group[-1]["item_name"],
                "category": group[-1]["category"],
                "score": round(score, 3),
                "score_percent": round(score * 100),
                "priority": priority,
                "expected_date": expected.isoformat(),
                "days_until": days_until,
                "reason": reason,
                "last_unit_price": float(group[-1]["unit_price"]),
                "purchase_count": len(group),
            }
        )
    predictions.sort(key=lambda item: (-item["score"], item["expected_date"], item["item_name"]))
    return predictions[:limit] if limit else predictions


def get_item_prediction(database_path, model_path, item_name):
    if not item_name:
        return None
    for item in predict_items(database_path, model_path):
        if item["item_name"].casefold() == item_name.casefold():
            return item
    return None