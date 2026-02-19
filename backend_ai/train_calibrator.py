import csv
import sys
from backend_ai.confidence_calibrator import fit_isotonic


def train_from_csv(path: str):
    preds = []
    labels = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Expect columns: predicted_confidence,correct (0/1 or true/false)
            p = float(r.get("predicted_confidence", 0))
            c = r.get("correct", "0")
            lab = 1 if str(c).strip().lower() in ("1", "true", "yes") else 0
            preds.append(p)
            labels.append(lab)

    if not preds:
        print("No data found in CSV")
        return
    fit_isotonic(preds, labels)
    print("Calibrator trained and saved.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend_ai.train_calibrator data.csv")
    else:
        train_from_csv(sys.argv[1])
