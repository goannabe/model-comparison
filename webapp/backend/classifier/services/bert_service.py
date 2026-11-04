import numpy as np
from django.conf import settings

from .common import Timer


class BERTService:
    name = "bert"
    confidence_type = "softmax"

    def __init__(self, label_encoder, model_dir=None):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        checkpoint_dir = model_dir or (settings.MODELS_DIR / "bert")
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(checkpoint_dir)
        self.model.to("cpu")
        self.model.eval()
        self.label_encoder = label_encoder

    def _to_result(self, probs_row, elapsed_ms):
        order = np.argsort(probs_row)[::-1]
        labels = self.label_encoder.classes_
        return {
            "predicted_label": labels[order[0]],
            "confidence_type": self.confidence_type,
            "probabilities": [
                {"label": labels[i], "score": float(probs_row[i])} for i in order
            ],
            "inference_ms": elapsed_ms,
        }

    def _predict_probs(self, texts, batch_size=16):
        torch = self._torch
        all_probs = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                chunk = texts[i : i + batch_size]
                inputs = self.tokenizer(
                    chunk, padding=True, truncation=True, max_length=512, return_tensors="pt"
                )
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).numpy()
                all_probs.append(probs)
        return np.concatenate(all_probs, axis=0)

    def predict_one(self, text):
        with Timer() as t:
            probs = self._predict_probs([text])[0]
        return self._to_result(probs, t.elapsed_ms)

    def predict_batch(self, texts):
        with Timer() as t:
            probs = self._predict_probs(texts)
        per_row_ms = t.elapsed_ms / max(len(texts), 1)
        return [self._to_result(probs[i], per_row_ms) for i in range(len(texts))]

    def explain(self, text):
        torch = self._torch

        inputs = self.tokenizer(text, truncation=True, max_length=512, return_tensors="pt")
        input_ids = inputs["input_ids"]

        embeddings = self.model.get_input_embeddings()(input_ids).detach()
        embeddings.requires_grad_(True)

        outputs = self.model(inputs_embeds=embeddings, attention_mask=inputs["attention_mask"])
        logits = outputs.logits[0]
        predicted_idx = int(torch.argmax(logits))

        self.model.zero_grad()
        logits[predicted_idx].backward()

        grads = embeddings.grad[0]  # (seq_len, hidden_dim)
        token_scores = (grads * embeddings[0]).sum(dim=-1).detach().numpy()

        tokens = self.tokenizer.convert_ids_to_tokens(input_ids[0])

        # Merge wordpiece continuations ("##ing") back into whole words by
        # summing their scores, so results read as real words to the user.
        words, scores = [], []
        for token, score in zip(tokens, token_scores):
            if token in (self.tokenizer.cls_token, self.tokenizer.sep_token, self.tokenizer.pad_token):
                continue
            if token.startswith("##") and words:
                words[-1] += token[2:]
                scores[-1] += float(score)
            else:
                words.append(token)
                scores.append(float(score))

        max_abs = max((abs(s) for s in scores), default=0.0)
        scale = max_abs or 1.0
        return {
            "tokens": [
                {"token": word, "score": score / scale} for word, score in zip(words, scores)
            ]
        }
