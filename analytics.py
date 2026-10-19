import pandas as pd

import database


def _purchase_frame(database_path):
    rows = database.get_purchase_history(database_path)
    columns = ["id", "item_name", "category", "quantity", "unit_price", "purchase_date"]
    frame = pd.DataFrame([dict(row) for row in rows], columns=columns)
    if not frame.empty:
        frame["purchase_date"] = pd.to_datetime(frame["purchase_date"])
        frame["spend"] = frame["quantity"] * frame["unit_price"]
        frame["month"] = frame["purchase_date"].dt.to_period("M").astype(str)
        frame["week"] = frame["purchase_date"].dt.to_period("W").astype(str)
    return frame


def get_analytics(database_path):
    frame = _purchase_frame(database_path)
    empty = {"labels": [], "values": []}
    if frame.empty:
        return {"monthly_spending": empty, "monthly_frequency": empty, "category_spending": empty, "top_items": empty}
    spending = frame.groupby("month")["spend"].sum().round(2)
    frequency = frame.groupby("month").size()
    categories = frame.groupby("category")["spend"].sum().sort_values(ascending=False)
    top_items = frame.groupby("item_name")["quantity"].sum().sort_values(ascending=False).head(8)
    return {
        "monthly_spending": {"labels": spending.index.tolist(), "values": spending.tolist()},
        "monthly_frequency": {"labels": frequency.index.tolist(), "values": frequency.tolist()},
        "category_spending": {"labels": categories.index.tolist(), "values": categories.round(2).tolist()},
        "top_items": {"labels": top_items.index.tolist(), "values": top_items.tolist()},
    }


def get_dashboard_charts(database_path):
    frame = _purchase_frame(database_path)
    if frame.empty:
        return {"weekly_spending": {"labels": [], "values": []}, "top_items": {"labels": [], "values": []}}
    weekly = frame.groupby("week")["spend"].sum().tail(8).round(2)
    top = frame.groupby("item_name")["quantity"].sum().sort_values(ascending=False).head(5)
    return {
        "weekly_spending": {"labels": weekly.index.tolist(), "values": weekly.tolist()},
        "top_items": {"labels": top.index.tolist(), "values": top.tolist()},
    }


def get_insights(database_path, predictions):
    frame = _purchase_frame(database_path)
    if frame.empty:
        return ["Add a purchase to start building your grocery insights."]
    insights = []
    category_spending = frame.groupby("category")["spend"].sum().sort_values(ascending=False)
    if len(category_spending):
        share = category_spending.iloc[0] / max(frame["spend"].sum(), 0.01) * 100
        insights.append(
            f"{category_spending.index[0]} leads spending at {share:.0f}% of recorded purchases."
        )
    recent = frame[frame["purchase_date"] >= frame["purchase_date"].max() - pd.Timedelta(days=30)]
    insights.append(f"{len(recent)} purchase entries were recorded in the latest 30-day window.")
    due_items = [item for item in predictions if item["priority"] == "HIGH"]
    if due_items:
        names = ", ".join(item["item_name"] for item in due_items[:3])
        insights.append(f"Restock soon: {names} based on your purchase rhythm.")
    else:
        insights.append("No items are currently at high restock priority.")
    return insights