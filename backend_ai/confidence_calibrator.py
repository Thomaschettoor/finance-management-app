import os
import joblib
from typing import Optional
from sklearn.isotonic import IsotonicRegression

MODEL_PATH = os.path.join(os.path.dirname(__file__), "calibrator_isotonic_v1.pkl")


def fit_isotonic(predictions, labels):
    """Fit an isotonic regression calibrator.

    predictions: iterable of model probabilities (0..1)
    labels: iterable of {0,1} correctness
    Returns the fitted IsotonicRegression object and saves it to disk.
    """
    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(list(predictions), list(labels))
    joblib.dump(ir, MODEL_PATH)
    return ir


def load_calibrator() -> Optional[IsotonicRegression]:
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            return None
    return None


def calibrate_prob(p: float) -> float:
    ir = load_calibrator()
    if ir is None:
        return p
    try:
        return float(ir.transform([p])[0])
    except Exception:
        return p
