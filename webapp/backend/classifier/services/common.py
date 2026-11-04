import pickle
import time

from django.conf import settings


def load_label_encoder():
    with open(settings.ARTIFACTS_DIR / "label_encoder.pkl", "rb") as f:
        return pickle.load(f)


class Timer:
    """Context manager measuring wall-clock duration in milliseconds."""

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
