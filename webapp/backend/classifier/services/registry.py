import logging
import time

from django.conf import settings

from .common import load_label_encoder

logger = logging.getLogger(__name__)

MODEL_SPECS = [
    # -------------------------------------------------------------------------
    # DEPLOY BRANCH (deploy-baseline): only the baseline model of each family
    # is served, to keep the Cloud Run instance small (memory, cold start and
    # image size). The variants are commented out, not deleted - their weights
    # still exist (models/weights/*_variants, and on the Hugging Face weights
    # repo) and the full 12-model setup lives on `main`. To re-enable a
    # variant, uncomment its entry here and add its folder to the weight
    # download in webapp/Dockerfile.backend.
    # -------------------------------------------------------------------------
    {"key": "svm", "family": "svm", "label": "SVM (base)",
     "module": "classifier.services.svm_service", "class_name": "SVMService", "model_dir": "svm"},
    # {"key": "svm_tuned", "family": "svm", "label": "SVM (tuned)",
    #  "module": "classifier.services.svm_service", "class_name": "SVMService",
    #  "model_dir": "svm_variants/tuned"},

    {"key": "lstm", "family": "lstm", "label": "LSTM (base)",
     "module": "classifier.services.lstm_service", "class_name": "LSTMService", "model_dir": "lstm"},
    # {"key": "lstm_units256", "family": "lstm", "label": "LSTM (units256)",
    #  "module": "classifier.services.lstm_service", "class_name": "LSTMService",
    #  "model_dir": "lstm_variants/units256"},
    # {"key": "lstm_dropout05", "family": "lstm", "label": "LSTM (dropout05)",
    #  "module": "classifier.services.lstm_service", "class_name": "LSTMService",
    #  "model_dir": "lstm_variants/dropout05"},
    # {"key": "lstm_lr5e-4", "family": "lstm", "label": "LSTM (lr5e-4)",
    #  "module": "classifier.services.lstm_service", "class_name": "LSTMService",
    #  "model_dir": "lstm_variants/lr5e-4"},
    # {"key": "lstm_embed256", "family": "lstm", "label": "LSTM (embed256)",
    #  "module": "classifier.services.lstm_service", "class_name": "LSTMService",
    #  "model_dir": "lstm_variants/embed256"},

    {"key": "bert", "family": "bert", "label": "BERT (base)",
     "module": "classifier.services.bert_service", "class_name": "BERTService", "model_dir": "bert"},
    # {"key": "bert_sweep_b_lr3e-5", "family": "bert", "label": "BERT (sweep_b_lr3e-5)",
    #  "module": "classifier.services.bert_service", "class_name": "BERTService",
    #  "model_dir": "bert_variants/sweep_b_lr3e-5"},
    # {"key": "bert_distilbert", "family": "bert", "label": "BERT (distilbert)",
    #  "module": "classifier.services.bert_service", "class_name": "BERTService",
    #  "model_dir": "bert_variants/distilbert"},

    {"key": "zeroshot", "family": "zeroshot", "label": "Zero-Shot (baseline)",
     "module": "classifier.services.zeroshot_service", "class_name": "ZeroShotService", "model_dir": None},
    # {"key": "zeroshot_tuned", "family": "zeroshot", "label": "Zero-Shot (tuned)",
    #  "module": "classifier.services.zeroshot_service", "class_name": "ZeroShotService", "model_dir": None,
    #  "init_kwargs": {
    #      "descriptive_label_map": {
    #          "Business": "business and finance",
    #          "Entertainment": "entertainment, celebrities, and movies",
    #          "Health": "health, wellness, and medicine",
    #          "Politics": "politics and government",
    #          "Science": "science and research",
    #          "Sports": "sports",
    #          "Technology": "technology",
    #          "World": "world news and international affairs",
    #      },
    #      "hypothesis_template": "This news article is about {}.",
    #  }},
]


class ModelRegistry:
    """Loads every model spec once and serves predictions from the in-memory
    instances. `load_all()` must be called exactly once at process startup
    (see classifier/apps.py) - never re-instantiate services per request."""

    def __init__(self):
        self.services = {}
        self.load_errors = {}
        self._loaded = False

    def load_all(self):
        if self._loaded:
            return
        self._loaded = True

        label_encoder = load_label_encoder()

        # Import lazily so a missing/broken dependency for one model doesn't
        # block the others, and so `django.conf.settings` is fully configured
        # before tensorflow/torch get imported.
        for spec in MODEL_SPECS:
            key = spec["key"]
            start = time.perf_counter()
            try:
                module = __import__(spec["module"], fromlist=[spec["class_name"]])
                service_cls = getattr(module, spec["class_name"])
                model_dir = settings.MODELS_DIR / spec["model_dir"] if spec["model_dir"] else None
                self.services[key] = service_cls(label_encoder, model_dir, **spec.get("init_kwargs", {}))
                elapsed = time.perf_counter() - start
                logger.info("Loaded %s model in %.1fs", key, elapsed)
            except Exception as exc:  # noqa: BLE001 - report any failure per model
                self.load_errors[key] = str(exc)
                logger.exception("Failed to load %s model", key)

    def status(self):
        return {
            spec["key"]: {"loaded": spec["key"] in self.services, "error": self.load_errors.get(spec["key"])}
            for spec in MODEL_SPECS
        }

    def model_list(self):
        return [
            {
                "key": spec["key"],
                "family": spec["family"],
                "label": spec["label"],
                "loaded": spec["key"] in self.services,
                "error": self.load_errors.get(spec["key"]),
            }
            for spec in MODEL_SPECS
        ]

    def predict_all(self, text):
        results = {}
        for key, service in self.services.items():
            results[key] = service.predict_one(text)
        return results

    def predict_all_batch(self, texts):
        results = {}
        for key, service in self.services.items():
            results[key] = service.predict_batch(texts)
        return results

    def explain_all(self, text):
        results = {}
        for key, service in self.services.items():
            results[key] = service.explain(text)
        return results


registry = ModelRegistry()
