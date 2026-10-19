from datetime import date
import os
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

import analytics
import database
import predictor


ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "smartbasket-local-demo-key"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(app.instance_path) / "smartbasket.sqlite3")
        ),
        SAMPLE_DATA=str(ROOT / "data" / "sample_data.csv"),
        MODEL_PATH=str(ROOT / "models" / "purchase_readiness.joblib"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database.init_db(app.config["DATABASE"], app.config["SAMPLE_DATA"])

    @app.get("/")
    def dashboard():
        summary = database.get_dashboard_summary(app.config["DATABASE"])
        charts = analytics.get_dashboard_charts(app.config["DATABASE"])
        predictions = predictor.predict_items(
            app.config["DATABASE"], app.config["MODEL_PATH"], limit=5
        )
        insights = analytics.get_insights(app.config["DATABASE"], predictions)
        return render_template(
            "dashboard.html",
            summary=summary,
            charts=charts,
            predictions=predictions,
            insights=insights,
            active="dashboard",
        )

    @app.route("/purchases", methods=["GET", "POST"])
    def purchases():
        if request.method == "POST":
            values, error = purchase_form_values(request.form)
            if error:
                flash(error, "error")
            else:
                database.create_purchase(app.config["DATABASE"], **values)
                flash("Purchase added to your history.", "success")
                return redirect(url_for("purchases"))
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        rows = database.list_purchases(app.config["DATABASE"], query, category)
        categories = database.get_categories(app.config["DATABASE"])
        return render_template(
            "purchases.html",
            purchases=rows,
            categories=categories,
            query=query,
            selected_category=category,
            today=date.today().isoformat(),
            active="purchases",
        )

    @app.route("/purchases/<int:purchase_id>/edit", methods=["GET", "POST"])
    def edit_purchase(purchase_id):
        row = database.get_purchase(app.config["DATABASE"], purchase_id)
        if row is None:
            flash("That purchase could not be found.", "error")
            return redirect(url_for("purchases"))
        if request.method == "POST":
            values, error = purchase_form_values(request.form)
            if error:
                flash(error, "error")
            else:
                database.update_purchase(app.config["DATABASE"], purchase_id, **values)
                flash("Purchase updated.", "success")
                return redirect(url_for("purchases"))
        return render_template("edit_purchase.html", purchase=row, active="purchases")

    @app.post("/purchases/<int:purchase_id>/delete")
    def delete_purchase(purchase_id):
        if database.delete_purchase(app.config["DATABASE"], purchase_id):
            flash("Purchase removed from your history.", "success")
        else:
            flash("That purchase could not be found.", "error")
        return redirect(url_for("purchases"))

    @app.get("/shopping-list")
    def shopping_list():
        predictions = [
            item
            for item in predictor.predict_items(
                app.config["DATABASE"], app.config["MODEL_PATH"]
            )
            if item["priority"] in {"HIGH", "MEDIUM"}
        ]
        listed_names = {
            row["item_name"].casefold()
            for row in database.get_shopping_list(app.config["DATABASE"], "open")
        }
        suggestions = [
            item for item in predictions if item["item_name"].casefold() not in listed_names
        ]
        return render_template(
            "shopping_list.html",
            suggestions=suggestions,
            open_items=database.get_shopping_list(app.config["DATABASE"], "open"),
            completed_items=database.get_shopping_list(app.config["DATABASE"], "purchased"),
            active="shopping-list",
        )

    @app.post("/shopping-list/add")
    def add_to_shopping_list():
        item_name = request.form.get("item_name", "").strip()
        item = predictor.get_item_prediction(
            app.config["DATABASE"], app.config["MODEL_PATH"], item_name
        )
        if item is None or item["priority"] == "LOW":
            flash("Only current HIGH or MEDIUM recommendations can be added.", "error")
        elif database.add_shopping_item(app.config["DATABASE"], item):
            flash(f"{item_name} added to your shopping list.", "success")
        else:
            flash(f"{item_name} is already on your open list.", "info")
        return redirect(url_for("shopping_list"))

    @app.post("/shopping-list/<int:item_id>/purchased")
    def mark_purchased(item_id):
        item = database.mark_shopping_item_purchased(app.config["DATABASE"], item_id)
        if item is None:
            flash("That list item could not be found.", "error")
        else:
            database.create_purchase(
                app.config["DATABASE"],
                item_name=item["item_name"],
                category=item["category"],
                quantity=1,
                unit_price=item["last_unit_price"],
                purchase_date=date.today().isoformat(),
                notes="Added from Smart Shopping List",
            )
            flash(f"{item['item_name']} marked purchased and added to history.", "success")
        return redirect(url_for("shopping_list"))

    @app.post("/shopping-list/<int:item_id>/remove")
    def remove_shopping_item(item_id):
        database.remove_shopping_item(app.config["DATABASE"], item_id)
        flash("Item removed from the shopping list.", "success")
        return redirect(url_for("shopping_list"))

    @app.get("/analytics")
    def analytics_page():
        return render_template(
            "analytics.html",
            charts=analytics.get_analytics(app.config["DATABASE"]),
            active="analytics",
        )

    return app


def purchase_form_values(form):
    item_name = form.get("item_name", "").strip()
    category = form.get("category", "").strip()
    purchase_date = form.get("purchase_date", "").strip()
    notes = form.get("notes", "").strip()
    try:
        quantity = float(form.get("quantity", ""))
        unit_price = float(form.get("unit_price", ""))
        date.fromisoformat(purchase_date)
    except (TypeError, ValueError):
        return None, "Enter a valid quantity, price, and purchase date."
    if not item_name or not category or quantity <= 0 or unit_price < 0:
        return None, "Item and category are required; quantity must be positive and price cannot be negative."
    return {
        "item_name": item_name,
        "category": category,
        "quantity": quantity,
        "unit_price": unit_price,
        "purchase_date": purchase_date,
        "notes": notes,
    }, None


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )