import json
import pickle

import numpy as np
from django.conf import settings

from .common import Timer


class LSTMService:
    name = "lstm"
    confidence_type = "softmax"

    def __init__(self, label_encoder, model_dir=None):
        import tensorflow as tf
        from tensorflow.keras.preprocessing.sequence import pad_sequences

        self._pad_sequences = pad_sequences

        model_dir = model_dir or (settings.MODELS_DIR / "lstm")
        with open(model_dir / "tokenizer.pkl", "rb") as f:
            self.tokenizer = pickle.load(f)
        with open(model_dir / "config.json") as f:
            self.max_len = json.load(f)["max_len"]
        self.model = tf.keras.models.load_model(model_dir / "lstm_model.keras")
        self.label_encoder = label_encoder

    def _to_padded(self, texts):
        seqs = self.tokenizer.texts_to_sequences(texts)
        return self._pad_sequences(seqs, maxlen=self.max_len, padding="post", truncating="post")

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

    def predict_one(self, text):
        with Timer() as t:
            padded = self._to_padded([text])
            probs = self.model.predict(padded, verbose=0)[0]
        return self._to_result(probs, t.elapsed_ms)

    def predict_batch(self, texts):
        with Timer() as t:
            padded = self._to_padded(texts)
            probs = self.model.predict(padded, batch_size=32, verbose=0)
        per_row_ms = t.elapsed_ms / max(len(texts), 1)
        return [self._to_result(probs[i], per_row_ms) for i in range(len(texts))]

    def explain(self, text):
        import tensorflow as tf

        padded = self._to_padded([text])
        input_ids = tf.constant(padded)

        embedding_layer = next(
            layer for layer in self.model.layers if isinstance(layer, tf.keras.layers.Embedding)
        )

        with tf.GradientTape() as tape:
            embeddings = embedding_layer(input_ids)
            tape.watch(embeddings)

            x = embeddings
            found_embedding = False
            for layer in self.model.layers:
                if layer is embedding_layer:
                    found_embedding = True
                    continue
                if not found_embedding:
                    continue
                x = layer(x)

            predicted_idx = int(tf.argmax(x[0]))
            target = x[0, predicted_idx]

        grads = tape.gradient(target, embeddings)[0]  # (max_len, embed_dim)
        token_scores = tf.reduce_sum(grads * embeddings[0], axis=-1).numpy()  # (max_len,)

        seq = self.tokenizer.texts_to_sequences([text])[0][: self.max_len]
        index_word = self.tokenizer.index_word

        max_abs = max((abs(s) for s in token_scores[: len(seq)]), default=0.0)
        scale = max_abs or 1.0
        tokens = [
            {"token": index_word.get(token_id, "<unk>"), "score": float(token_scores[i] / scale)}
            for i, token_id in enumerate(seq)
        ]
        return {"tokens": tokens}
