import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd


@contextmanager
def connect(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(database_path, sample_data_path=None):
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL COLLATE NOCASE,
                category TEXT NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                purchase_date TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date);
            CREATE INDEX IF NOT EXISTS idx_purchases_item ON purchases(item_name);
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL COLLATE NOCASE,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                score REAL NOT NULL,
                expected_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                last_unit_price REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'purchased')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_open_shopping_item
                ON shopping_list(item_name COLLATE NOCASE) WHERE status = 'open';
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        seeded = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'sample_data_seeded'"
        ).fetchone()
        if not seeded:
            if sample_data_path and Path(sample_data_path).exists():
                sample_data = pd.read_csv(sample_data_path)
                sample_data = sample_data.fillna("")
                connection.executemany(
                    """INSERT INTO purchases
                       (item_name, category, quantity, unit_price, purchase_date, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            str(row.item_name),
                            str(row.category),
                            float(row.quantity),
                            float(row.unit_price),
                            str(row.purchase_date),
                            str(row.notes),
                        )
                        for row in sample_data.itertuples(index=False)
                    ],
                )
            connection.execute(
                "INSERT INTO app_meta (key, value) VALUES ('sample_data_seeded', '1')"
            )


def create_purchase(database_path, **purchase):
    with connect(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO purchases
               (item_name, category, quantity, unit_price, purchase_date, notes)
               VALUES (:item_name, :category, :quantity, :unit_price, :purchase_date, :notes)""",
            purchase,
        )
        return cursor.lastrowid


def list_purchases(database_path, query="", category=""):
    sql = "SELECT * FROM purchases WHERE 1 = 1"
    params = []
    if query:
        sql += " AND (item_name LIKE ? OR category LIKE ? OR notes LIKE ?)"
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY purchase_date DESC, id DESC"
    with connect(database_path) as connection:
        return connection.execute(sql, params).fetchall()


def get_purchase(database_path, purchase_id):
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT * FROM purchases WHERE id = ?", (purchase_id,)
        ).fetchone()


def update_purchase(database_path, purchase_id, **purchase):
    with connect(database_path) as connection:
        cursor = connection.execute(
            """UPDATE purchases SET item_name = :item_name, category = :category,
               quantity = :quantity, unit_price = :unit_price,
               purchase_date = :purchase_date, notes = :notes WHERE id = :id""",
            {**purchase, "id": purchase_id},
        )
        return cursor.rowcount > 0


def delete_purchase(database_path, purchase_id):
    with connect(database_path) as connection:
        cursor = connection.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
        return cursor.rowcount > 0


def get_categories(database_path):
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT DISTINCT category FROM purchases ORDER BY category COLLATE NOCASE"
        ).fetchall()
        return [row["category"] for row in rows]


def get_purchase_history(database_path):
    with connect(database_path) as connection:
        return connection.execute(
            """SELECT id, item_name, category, quantity, unit_price, purchase_date
               FROM purchases ORDER BY item_name COLLATE NOCASE, purchase_date, id"""
        ).fetchall()


def get_dashboard_summary(database_path):
    with connect(database_path) as connection:
        totals = connection.execute(
            """SELECT COUNT(*) AS total_purchases,
                      COALESCE(SUM(quantity * unit_price), 0) AS total_spending,
                      COUNT(DISTINCT item_name) AS unique_items
               FROM purchases"""
        ).fetchone()
        most_purchased = connection.execute(
            """SELECT item_name, SUM(quantity) AS quantity, COUNT(*) AS visits,
                      COALESCE(SUM(quantity * unit_price), 0) AS spend
               FROM purchases GROUP BY item_name
               ORDER BY quantity DESC, visits DESC LIMIT 5"""
        ).fetchall()
        latest = connection.execute(
            "SELECT MAX(purchase_date) AS latest_purchase FROM purchases"
        ).fetchone()["latest_purchase"]
        return {
            "total_purchases": totals["total_purchases"],
            "total_spending": float(totals["total_spending"]),
            "unique_items": totals["unique_items"],
            "average_basket": float(totals["total_spending"])
            / max(totals["total_purchases"], 1),
            "most_purchased": most_purchased,
            "latest_purchase": latest,
        }


def get_shopping_list(database_path, status=None):
    sql = "SELECT * FROM shopping_list"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY CASE priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, expected_date"
    with connect(database_path) as connection:
        return connection.execute(sql, params).fetchall()


def add_shopping_item(database_path, item):
    try:
        with connect(database_path) as connection:
            connection.execute(
                """INSERT INTO shopping_list
                   (item_name, category, priority, score, expected_date, reason, last_unit_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["item_name"],
                    item["category"],
                    item["priority"],
                    item["score"],
                    item["expected_date"],
                    item["reason"],
                    item["last_unit_price"],
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def mark_shopping_item_purchased(database_path, item_id):
    with connect(database_path) as connection:
        item = connection.execute(
            "SELECT * FROM shopping_list WHERE id = ? AND status = 'open'", (item_id,)
        ).fetchone()
        if item is None:
            return None
        connection.execute(
            "UPDATE shopping_list SET status = 'purchased' WHERE id = ?", (item_id,)
        )
        return item


def remove_shopping_item(database_path, item_id):
    with connect(database_path) as connection:
        cursor = connection.execute("DELETE FROM shopping_list WHERE id = ?", (item_id,))
        return cursor.rowcount > 0