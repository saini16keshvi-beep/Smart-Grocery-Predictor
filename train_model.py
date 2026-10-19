from pathlib import Path

import joblib

import database
from predictor import _signature, train_classifier


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "instance" / "smartbasket.sqlite3"
MODEL_PATH = ROOT / "models" / "purchase_readiness.joblib"


def main():
    database.init_db(DATABASE_PATH, ROOT / "data" / "sample_data.csv")
    history = database.get_purchase_history(DATABASE_PATH)
    model, details = train_classifier(history)
    if model is None:
        print(f"Not enough varied purchase history to train a classifier: {details}")
        return
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "signature": _signature(history), "details": details}, MODEL_PATH)
    print(f"Saved Logistic Regression model to {MODEL_PATH}")
    print(f"Training samples: {details['samples']}; classes: {details['classes']}")


if __name__ == "__main__":
    main()