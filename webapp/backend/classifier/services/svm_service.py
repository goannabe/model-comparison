import json
import pickle

import numpy as np
from django.conf import settings
from scipy.special import softmax

from .common import Timer


class SVMService:
    name = "svm"
    confidence_type = "margin_softmax"

    def __init__(self, label_encoder, model_dir=None):
        model_dir = model_dir or (settings.MODELS_DIR / "svm")
        with open(model_dir / "svm_model.pkl", "rb") as f:
            self.model = pickle.load(f)
        with open(model_dir / "vectorizer.pkl", "rb") as f:
            self.vectorizer = pickle.load(f)
        with open(model_dir / "config.json") as f:
            self.config = json.load(f)
        self.label_encoder = label_encoder

    def _to_result(self, margins_row, elapsed_ms):
        probs = softmax(margins_row)
        order = np.argsort(probs)[::-1]
        labels = self.label_encoder.classes_
        return {
            "predicted_label": labels[order[0]],
            "confidence_type": self.confidence_type,
            "probabilities": [
                {"label": labels[i], "score": float(probs[i])} for i in order
            ],
            "inference_ms": elapsed_ms,
        }

    def predict_one(self, text):
        with Timer() as t:
            X = self.vectorizer.transform([text])
            margins = self.model.decision_function(X)
        return self._to_result(margins[0], t.elapsed_ms)

    def predict_batch(self, texts):
        with Timer() as t:
            X = self.vectorizer.transform(texts)
            margins = self.model.decision_function(X)
        # Split the total batch time across rows for a per-row timing figure,
        # since decision_function runs as one vectorized matrix operation.
        per_row_ms = t.elapsed_ms / max(len(texts), 1)
        return [self._to_result(margins[i], per_row_ms) for i in range(len(texts))]

    def explain(self, text):
        # Linear model over TF-IDF, so importance per token is exactly
        # tfidf_value * coef[predicted_class] - no gradients needed.
        X = self.vectorizer.transform([text])
        margins = self.model.decision_function(X)[0]
        predicted_idx = int(np.argmax(margins))

        coef = self.model.coef_
        # decision_function returns a scalar per sample for binary problems but
        # coef_ has shape (1, n_features) in that case - guard against it even
        # though this project is multiclass.
        class_coef = coef[predicted_idx] if coef.shape[0] > 1 else coef[0]

        feature_names = self.vectorizer.get_feature_names_out()
        row = X.tocoo()
        contributions = [
            (feature_names[col], float(X[0, col]) * float(class_coef[col]))
            for col in row.col
        ]
        contributions.sort(key=lambda pair: abs(pair[1]), reverse=True)

        max_abs = max((abs(score) for _, score in contributions), default=0.0)
        scale = max_abs or 1.0
        return {
            "tokens": [
                {"token": token, "score": score / scale} for token, score in contributions
            ]
        }
