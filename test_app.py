import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app
import database
import predictor


ROOT = Path(__file__).resolve().parents[1]


class SmartBasketTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database_path,
                "SAMPLE_DATA": str(ROOT / "data" / "sample_data.csv"),
                "MODEL_PATH": str(Path(self.temp_dir.name) / "missing.joblib"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seeded_dashboard_and_analytics_render_from_database(self):
        summary = database.get_dashboard_summary(self.database_path)
        self.assertGreater(summary["total_purchases"], 80)
        self.assertGreater(summary["total_spending"], 0)
        self.assertGreater(summary["unique_items"], 5)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/analytics").status_code, 200)

    def test_environment_database_is_initialized_and_seeded(self):
        environment_database = str(Path(self.temp_dir.name) / "render.sqlite3")
        with patch.dict("os.environ", {"DATABASE_PATH": environment_database}):
            configured_app = create_app()
        self.assertEqual(configured_app.config["DATABASE"], environment_database)
        self.assertGreater(database.get_dashboard_summary(environment_database)["total_purchases"], 0)

    def test_purchase_create_search_edit_and_delete(self):
        response = self.client.post(
            "/purchases",
            data={
                "item_name": "Test oranges",
                "category": "Produce",
                "quantity": "2",
                "unit_price": "1.25",
                "purchase_date": "2026-09-28",
                "notes": "Test entry",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        rows = database.list_purchases(self.database_path, "Test oranges")
        self.assertEqual(len(rows), 1)
        purchase_id = rows[0]["id"]
        self.assertEqual(rows[0]["quantity"] * rows[0]["unit_price"], 2.5)
        self.assertEqual(
            self.client.post(
                f"/purchases/{purchase_id}/edit",
                data={
                    "item_name": "Navel oranges",
                    "category": "Produce",
                    "quantity": "3",
                    "unit_price": "1.5",
                    "purchase_date": "2026-09-28",
                    "notes": "Updated",
                },
                follow_redirects=True,
            ).status_code,
            200,
        )
        self.assertEqual(database.get_purchase(self.database_path, purchase_id)["item_name"], "Navel oranges")
        self.assertTrue(database.delete_purchase(self.database_path, purchase_id))
        self.assertIsNone(database.get_purchase(self.database_path, purchase_id))

    def test_predictions_and_shopping_list_record_completed_purchase(self):
        predictions = predictor.predict_items(
            self.database_path, today=date(2026, 9, 29)
        )
        self.assertGreater(len(predictions), 5)
        self.assertTrue(all(0 <= item["score"] <= 1 for item in predictions))
        self.assertTrue(all(item["priority"] in {"HIGH", "MEDIUM", "LOW"} for item in predictions))
        candidate = next(item for item in predictions if item["priority"] in {"HIGH", "MEDIUM"})
        self.assertTrue(database.add_shopping_item(self.database_path, candidate))
        item = database.get_shopping_list(self.database_path, "open")[0]
        before = database.get_dashboard_summary(self.database_path)["total_purchases"]
        response = self.client.post(f"/shopping-list/{item['id']}/purchased", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(database.get_dashboard_summary(self.database_path)["total_purchases"], before + 1)
        self.assertEqual(len(database.get_shopping_list(self.database_path, "purchased")), 1)

    def test_invalid_purchase_is_rejected(self):
        response = self.client.post(
            "/purchases",
            data={"item_name": "Bad", "category": "Pantry", "quantity": "0", "unit_price": "2", "purchase_date": "2026-09-28"},
            follow_redirects=True,
        )
        self.assertIn(b"quantity must be positive", response.data)


if __name__ == "__main__":
    unittest.main()