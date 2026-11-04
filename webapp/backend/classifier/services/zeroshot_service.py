import re

from .common import Timer


class ZeroShotService:
    name = "zeroshot"
    confidence_type = "softmax"

    def __init__(self, label_encoder, model_dir=None, descriptive_label_map=None, hypothesis_template=None):
        from transformers import pipeline

        self.label_encoder = label_encoder
        label_order = list(label_encoder.classes_)
        self.descriptive_label_map = descriptive_label_map or {c: c for c in label_order}
        self.candidate_labels = [self.descriptive_label_map[c] for c in label_order]
        self.phrase_to_label = {v: k for k, v in self.descriptive_label_map.items()}
        self.hypothesis_template = hypothesis_template or "This text is about {}."
        self.pipe = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

    def _to_result(self, phrases, scores, elapsed_ms):
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        labels = [self.phrase_to_label[p] for p in phrases]
        return {
            "predicted_label": labels[order[0]],
            "confidence_type": self.confidence_type,
            "probabilities": [{"label": labels[i], "score": float(scores[i])} for i in order],
            "inference_ms": elapsed_ms,
        }

    def predict_one(self, text):
        with Timer() as t:
            out = self.pipe(text, self.candidate_labels, hypothesis_template=self.hypothesis_template)
        return self._to_result(out["labels"], out["scores"], t.elapsed_ms)

    def predict_batch(self, texts):
        with Timer() as t:
            outs = self.pipe(texts, self.candidate_labels, hypothesis_template=self.hypothesis_template)
        per_row_ms = t.elapsed_ms / max(len(texts), 1)
        return [self._to_result(out["labels"], out["scores"], per_row_ms) for out in outs]

    def explain(self, text):
        # No gradients available through the pipeline API, so importance is
        # measured by occlusion: how much the predicted label's entailment
        # score drops when each word is removed from the input.
        words = re.findall(r"\S+", text)
        if not words:
            return {"tokens": []}

        baseline = self.pipe(text, self.candidate_labels, hypothesis_template=self.hypothesis_template)
        predicted_phrase = baseline["labels"][0]
        base_score = baseline["scores"][baseline["labels"].index(predicted_phrase)]

        variants = [" ".join(words[:i] + words[i + 1 :]) or words[i] for i in range(len(words))]
        outs = self.pipe(variants, [predicted_phrase], hypothesis_template=self.hypothesis_template)
        if isinstance(outs, dict):
            outs = [outs]

        scores = [base_score - out["scores"][out["labels"].index(predicted_phrase)] for out in outs]

        max_abs = max((abs(s) for s in scores), default=0.0)
        scale = max_abs or 1.0
        return {
            "tokens": [
                {"token": word, "score": score / scale} for word, score in zip(words, scores)
            ]
        }
