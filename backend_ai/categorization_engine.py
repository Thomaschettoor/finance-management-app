import joblib
import numpy as np
import os

# Load model once
MODEL_PATH = os.path.join(os.path.dirname(__file__), "transaction_model_v1.pkl")
model = joblib.load(MODEL_PATH)

def predict_transaction(text, threshold=0.65):
    prob = model.predict_proba([text])[0]
    classes = model.classes_

    top_indices = np.argsort(prob)[::-1][:3]

    primary_class = classes[top_indices[0]]
    primary_conf = float(prob[top_indices[0]])

    return {
        "status": "AUTO" if primary_conf >= threshold else "REVIEW",
        "primary": primary_class,
        "primary_confidence": primary_conf,
        "suggestion_2": classes[top_indices[1]],
        "suggestion_2_confidence": float(prob[top_indices[1]]),
        "suggestion_3": classes[top_indices[2]],
        "suggestion_3_confidence": float(prob[top_indices[2]])
    }
