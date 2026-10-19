# SmartBasket - Smart Grocery Predictor

SmartBasket is a local Flask application for tracking grocery purchases, reviewing spending, and estimating upcoming restocks from a household's purchase history. SQLite stores purchases and shopping-list changes in `instance/smartbasket.sqlite3`.

## Run it

Python 3.10 or newer is recommended.

```powershell
uv venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv run python app.py
```

Open http://127.0.0.1:5000. The app binds to `0.0.0.0` and reads its port from `PORT` (default `5000`). On first run, the sample CSV is imported into SQLite once. The sample records are editable and removable like any other purchase. To train and save a Logistic Regression artifact from the current database, run:

```powershell
uv run python train_model.py
```

The app also trains from the live database when predictions are requested, and uses a transparent purchase-cycle score when there is not enough varied history to fit a classifier.

## Features

- Dashboard metrics, top items, charts, and data-derived restock insights.
- Purchase create, edit, delete, search, and category filtering.
- Per-item restock estimates with model score, priority, expected date, and explanation.
- Shopping list recommendations; marking an item purchased records a new purchase at its last observed unit price.
- Monthly spending, purchase frequency, category spending, and popular-item charts.
- SQLite persistence with a one-time sample-data seed.

## Project layout

```text
app.py                 Flask routes and form validation
database.py            SQLite schema, seed, and data operations
predictor.py           History features and Logistic Regression predictions
analytics.py           Pandas-based metrics and insights
train_model.py         Train and save the current prediction model
data/sample_data.csv   Starter purchase history
models/                Saved model artifacts
templates/             Jinja pages
static/                Styles and browser-side charts
tests/                 Flask and database integration tests
```

Charts use Chart.js from its public CDN; the rest of the application runs locally.

## Deploy to Render

The included `render.yaml` configures Gunicorn, a generated secret key, and a persistent disk mounted at `/var/data`. The disk keeps SQLite data across deploys; Render persistent disks require a paid web-service plan. Deploy the repository as a Blueprint in Render and confirm the plan and disk before creating the service.

For a manual Web Service, use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT app:app`
- Add a persistent disk mounted at `/var/data` and set `DATABASE_PATH=/var/data/smartbasket.sqlite3`.
- Set `SECRET_KEY` to a long random value.

SQLite tables are created automatically when the app starts. The starter CSV is loaded only once into a new database; when a persistent database already exists, deployment leaves its records unchanged.

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```