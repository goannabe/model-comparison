"""Credit limits and per-model selection.

Run (no real models are loaded - fakes stand in for them):
    DJANGO_SKIP_MODEL_LOAD=1 python manage.py test classifier
"""

import io

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from classifier.quota import HourlyQuota, QuotaExceeded, client_id_for, reset_quota_singleton
from classifier.services.registry import registry


class FakeClock:
    def __init__(self, now=10_000.0):
        self.now = now

    def __call__(self):
        return self.now


class HourlyQuotaTests(SimpleTestCase):
    def setUp(self):
        self.clock = FakeClock(3600 * 5 + 100)  # 100 s into an hour
        self.quota = HourlyQuota(per_client_limit=10, global_limit=15, clock=self.clock)

    def test_charge_spends_from_both_budgets(self):
        status = self.quota.charge("a", 4)
        self.assertEqual(status["used"], 4)
        self.assertEqual(status["remaining"], 6)
        self.assertEqual(status["global_remaining"], 11)
        self.assertEqual(status["reset_in_seconds"], 3500)

    def test_client_limit_rejects_without_spending(self):
        self.quota.charge("a", 8)
        with self.assertRaises(QuotaExceeded) as ctx:
            self.quota.charge("a", 3)
        self.assertEqual(ctx.exception.scope, "client")
        self.assertEqual(self.quota.status("a")["used"], 8)  # nothing partially spent

    def test_global_limit_applies_across_clients(self):
        self.quota.charge("a", 10)
        with self.assertRaises(QuotaExceeded) as ctx:
            self.quota.charge("b", 6)
        self.assertEqual(ctx.exception.scope, "global")
        self.quota.charge("b", 5)  # exactly fills the global budget
        self.assertEqual(self.quota.status("c")["global_remaining"], 0)

    def test_new_hour_resets_everything(self):
        self.quota.charge("a", 10)
        self.clock.now += 3500  # top of the next hour
        status = self.quota.status("a")
        self.assertEqual(status["remaining"], 10)
        self.assertEqual(status["global_remaining"], 15)
        self.assertEqual(status["reset_in_seconds"], 3600)

    def test_refund_and_reset_scopes(self):
        self.quota.charge("a", 5)
        self.quota.charge("b", 5)
        self.quota.refund("a", 2)
        self.assertEqual(self.quota.status("a")["used"], 3)
        self.quota.reset(scope="client", client_id="a")
        self.assertEqual(self.quota.status("a")["used"], 0)
        self.assertEqual(self.quota.status("b")["used"], 5)
        self.assertEqual(self.quota.status("b")["global_remaining"], 7)
        self.quota.reset(scope="global")
        self.assertEqual(self.quota.status("b")["global_remaining"], 15)
        self.assertEqual(self.quota.status("b")["used"], 5)
        self.quota.reset()
        self.assertEqual(self.quota.status("b")["used"], 0)


class ClientIdTests(SimpleTestCase):
    def test_uses_last_forwarded_entry(self):
        class Req:
            META = {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 203.0.113.9", "REMOTE_ADDR": "10.0.0.1"}

        self.assertEqual(client_id_for(Req), "203.0.113.9")

    def test_falls_back_to_remote_addr(self):
        class Req:
            META = {"REMOTE_ADDR": "10.0.0.1"}

        self.assertEqual(client_id_for(Req), "10.0.0.1")


class FakeService:
    def __init__(self, label="Business", fail=False):
        self.calls = []
        self.label = label
        self.fail = fail

    def _result(self):
        return {
            "predicted_label": self.label,
            "confidence_type": "softmax",
            "probabilities": [{"label": self.label, "score": 0.9}],
            "inference_ms": 1.0,
        }

    def predict_one(self, text):
        self.calls.append(("predict", text))
        if self.fail:
            raise RuntimeError("model crashed")
        return self._result()

    def predict_batch(self, texts):
        self.calls.append(("batch", len(texts)))
        return [self._result() for _ in texts]

    def explain(self, text):
        self.calls.append(("explain", text))
        return {"tokens": [{"token": "word", "score": 1.0}]}


QUOTA_ON = dict(
    QUOTA_ENABLED=True,
    QUOTA_PER_CLIENT_PER_HOUR=10,
    QUOTA_GLOBAL_PER_HOUR=100,
    QUOTA_ADMIN_KEY="test-admin-key",
)


class ApiTestBase(SimpleTestCase):
    def setUp(self):
        self._saved_services = registry.services
        self.svm, self.bert, self.zeroshot = FakeService(), FakeService(), FakeService()
        registry.services = {"svm": self.svm, "bert": self.bert, "zeroshot": self.zeroshot}
        reset_quota_singleton()
        self.client = APIClient()

    def tearDown(self):
        registry.services = self._saved_services
        reset_quota_singleton()

    def predict(self, models, text="Stocks rallied today", **extra):
        return self.client.post("/api/predict/", {"text": text, "models": models}, format="json", **extra)


@override_settings(**QUOTA_ON)
class PredictApiTests(ApiTestBase):
    def test_runs_only_selected_models_and_charges_their_cost(self):
        response = self.predict(["svm", "bert"])  # 1 + 2 credits
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["results"]), {"svm", "bert"})
        self.assertEqual(self.zeroshot.calls, [])  # unselected model never ran
        self.assertEqual(response.data["cost"], 3)
        self.assertEqual(response.data["quota"]["remaining"], 7)
        self.assertNotIn("tokens", response.data["results"]["svm"])  # no explanation in predict

    def test_rejects_when_out_of_credits(self):
        self.assertEqual(self.predict(["zeroshot", "zeroshot", "bert"]).data["cost"], 6)  # dupes dropped
        response = self.predict(["zeroshot", "svm"])  # needs 5, has 4
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["scope"], "client")
        self.assertEqual(response.data["quota"]["remaining"], 4)
        self.assertIn("Retry-After", response)
        self.assertEqual(len(self.svm.calls), 0)

    def test_visitors_have_separate_budgets(self):
        self.predict(["zeroshot"], HTTP_X_FORWARDED_FOR="198.51.100.1")  # 4
        self.predict(["zeroshot", "bert"], HTTP_X_FORWARDED_FOR="198.51.100.1")  # + 6 = 10 used
        self.assertEqual(self.predict(["svm"], HTTP_X_FORWARDED_FOR="198.51.100.1").status_code, 429)
        self.assertEqual(self.predict(["svm"], HTTP_X_FORWARDED_FOR="198.51.100.2").status_code, 200)

    @override_settings(QUOTA_GLOBAL_PER_HOUR=5)
    def test_global_budget_caps_everyone(self):
        reset_quota_singleton()
        self.assertEqual(self.predict(["zeroshot"], HTTP_X_FORWARDED_FOR="198.51.100.1").status_code, 200)
        response = self.predict(["bert"], HTTP_X_FORWARDED_FOR="198.51.100.2")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["scope"], "global")

    def test_failed_model_refunds_credits(self):
        self.bert.fail = True
        self.client.raise_request_exception = False
        response = self.predict(["bert"])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.client.get("/api/quota/").data["remaining"], 10)

    def test_requires_at_least_one_known_model(self):
        self.assertEqual(self.predict([]).status_code, 400)
        self.assertEqual(self.predict(["nope"]).status_code, 400)

    @override_settings(MAX_TEXT_CHARS=10)
    def test_rejects_overlong_text(self):
        self.assertEqual(self.predict(["svm"], text="x" * 11).status_code, 400)


@override_settings(**QUOTA_ON)
class ExplainApiTests(ApiTestBase):
    def explain(self, models):
        return self.client.post("/api/predict/explain/", {"text": "Stocks rallied", "models": models}, format="json")

    def test_explains_only_the_requested_model(self):
        response = self.explain(["bert"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data["results"]), ["bert"])
        self.assertEqual(response.data["cost"], 4)
        self.assertEqual(self.svm.calls, [])

    def test_zero_shot_explain_is_not_available(self):
        response = self.explain(["zeroshot"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.zeroshot.calls, [])

    def test_model_list_reports_costs_and_explainability(self):
        by_key = {m["key"]: m for m in self.client.get("/api/models/").data["models"]}
        self.assertEqual(by_key["bert"]["cost"], {"predict": 2, "explain": 4})
        self.assertFalse(by_key["zeroshot"]["explainable"])
        self.assertIsNone(by_key["zeroshot"]["cost"]["explain"])


@override_settings(**QUOTA_ON)
class BatchApiTests(ApiTestBase):
    def batch(self, rows, models):
        csv = io.BytesIO(("text\n" + "\n".join(rows)).encode())
        csv.name = "rows.csv"
        return self.client.post("/api/predict/batch/", {"file": csv, "models": models}, format="multipart")

    def test_cost_is_per_row(self):
        response = self.batch(["a", "b", "c"], ["svm", "bert"])  # 3 rows x 3 credits
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cost"], 9)
        self.assertEqual(self.zeroshot.calls, [])

    def test_rejects_batch_over_budget(self):
        response = self.batch(["a", "b", "c"], ["zeroshot"])  # 12 > 10
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.zeroshot.calls, [])

    @override_settings(BATCH_MAX_ROWS=2)
    def test_row_limit(self):
        self.assertEqual(self.batch(["a", "b", "c"], ["svm"]).status_code, 400)


@override_settings(**QUOTA_ON)
class QuotaResetTests(ApiTestBase):
    def reset(self, key=None, **body):
        headers = {"HTTP_X_ADMIN_KEY": key} if key is not None else {}
        return self.client.post("/api/quota/reset/", body, format="json", **headers)

    def test_requires_correct_key(self):
        self.assertEqual(self.reset().status_code, 403)
        self.assertEqual(self.reset("wrong").status_code, 403)

    @override_settings(QUOTA_ADMIN_KEY="")
    def test_disabled_without_configured_key(self):
        self.assertEqual(self.reset("").status_code, 403)

    def test_reset_restores_credits(self):
        self.predict(["zeroshot", "bert"])  # 6 credits
        self.assertEqual(self.client.get("/api/quota/").data["remaining"], 4)
        response = self.reset("test-admin-key")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/quota/").data["remaining"], 10)

    def test_reset_one_client(self):
        self.predict(["zeroshot"], HTTP_X_FORWARDED_FOR="198.51.100.1")
        self.predict(["zeroshot"], HTTP_X_FORWARDED_FOR="198.51.100.2")
        self.reset("test-admin-key", scope="client", client="198.51.100.1")
        remaining = lambda ip: self.client.get("/api/quota/", HTTP_X_FORWARDED_FOR=ip).data["remaining"]
        self.assertEqual(remaining("198.51.100.1"), 10)
        self.assertEqual(remaining("198.51.100.2"), 6)


@override_settings(QUOTA_ENABLED=False)
class QuotaDisabledTests(ApiTestBase):
    def test_never_limits_and_reports_disabled(self):
        for _ in range(20):
            self.assertEqual(self.predict(["zeroshot"]).status_code, 200)
        self.assertEqual(self.client.get("/api/quota/").data, {"enabled": False})
