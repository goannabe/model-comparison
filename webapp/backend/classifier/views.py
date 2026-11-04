import hmac
import math
import time

import pandas as pd
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .quota import QuotaExceeded, client_id_for, cost_for, get_quota
from .serializers import BatchPredictRequestSerializer, ExplainRequestSerializer, PredictRequestSerializer
from .services.registry import registry


def _families(keys):
    return [registry.family_of(k) for k in keys]


def _quota_exceeded_response(exc):
    minutes = max(1, math.ceil(exc.status["reset_in_seconds"] / 60))
    if exc.scope == "global":
        message = (
            "The demo has reached its shared usage limit for this hour. "
            f"Please try again in about {minutes} min."
        )
    else:
        message = (
            f"This request needs {exc.cost} credits but you have {exc.status['remaining']} "
            f"left this hour. Credits reset in about {minutes} min."
        )
    response = Response({"error": message, "scope": exc.scope, "quota": exc.status}, status=429)
    response["Retry-After"] = str(exc.status["reset_in_seconds"])
    return response


def _charge_and_run(request, cost, run):
    """Spend `cost` credits for this visitor, then run the work. Credits are
    refunded if the work raises, so a server error never costs the visitor."""
    quota = get_quota()
    client_id = client_id_for(request)
    try:
        status = quota.charge(client_id, cost)
    except QuotaExceeded as exc:
        return None, _quota_exceeded_response(exc)
    try:
        return (run(), status), None
    except Exception:
        quota.refund(client_id, cost)
        raise


@api_view(["GET"])
def health(request):
    return Response({"models": registry.status()})


@api_view(["GET"])
def models(request):
    return Response(
        {
            "models": registry.model_list(),
            "limits": {
                "max_text_chars": settings.MAX_TEXT_CHARS,
                "batch_max_rows": settings.BATCH_MAX_ROWS,
            },
        }
    )


@api_view(["GET"])
def quota(request):
    return Response(get_quota().status(client_id_for(request)))


@api_view(["POST"])
def quota_reset(request):
    """Admin-only: reset credit counters before the hour is up.

    Header  X-Admin-Key: <QUOTA_ADMIN_KEY>
    Body    {"scope": "all" | "global" | "client", "client": "<ip>"}  (optional,
            default scope "all"; "client" without an ip resets the caller)
    """
    admin_key = settings.QUOTA_ADMIN_KEY
    if not admin_key:
        return Response({"error": "Quota reset is disabled (QUOTA_ADMIN_KEY is not set)."}, status=403)
    provided = request.headers.get("X-Admin-Key", "")
    if not hmac.compare_digest(provided.encode(), admin_key.encode()):
        return Response({"error": "Invalid admin key."}, status=403)

    scope = request.data.get("scope", "all")
    if scope not in ("all", "global", "client"):
        return Response({"error": "scope must be 'all', 'global' or 'client'."}, status=400)
    client = request.data.get("client") or client_id_for(request)
    get_quota().reset(scope=scope, client_id=client)
    return Response({"reset": scope, **({"client": client} if scope == "client" else {})})


@api_view(["POST"])
def predict(request):
    serializer = PredictRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    text = serializer.validated_data["text"]
    keys = serializer.validated_data["models"]
    cost = cost_for("predict", _families(keys))

    start = time.perf_counter()
    outcome, error = _charge_and_run(request, cost, lambda: registry.predict(text, keys))
    if error:
        return error
    results, status = outcome
    total_ms = (time.perf_counter() - start) * 1000

    return Response({"input_text": text, "results": results, "total_ms": total_ms, "cost": cost, "quota": status})


@api_view(["POST"])
def predict_explain(request):
    serializer = ExplainRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    text = serializer.validated_data["text"]
    keys = serializer.validated_data["models"]
    cost = cost_for("explain", _families(keys))

    start = time.perf_counter()
    outcome, error = _charge_and_run(request, cost, lambda: registry.explain(text, keys))
    if error:
        return error
    results, status = outcome
    total_ms = (time.perf_counter() - start) * 1000

    return Response({"input_text": text, "results": results, "total_ms": total_ms, "cost": cost, "quota": status})


@api_view(["POST"])
def predict_batch(request):
    serializer = BatchPredictRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    uploaded_file = serializer.validated_data["file"]
    keys = serializer.validated_data["models"]

    if uploaded_file.size > settings.BATCH_MAX_FILE_SIZE_BYTES:
        return Response(
            {
                "error": f"File too large ({uploaded_file.size} bytes). "
                f"Max allowed is {settings.BATCH_MAX_FILE_SIZE_BYTES} bytes."
            },
            status=400,
        )

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:  # noqa: BLE001
        return Response({"error": f"Could not parse CSV: {exc}"}, status=400)

    if "text" not in df.columns:
        return Response(
            {
                "error": "CSV must contain a 'text' column.",
                "columns_found": list(df.columns),
            },
            status=400,
        )

    skipped_rows = df.index[df["text"].isna() | (df["text"].astype(str).str.strip() == "")].tolist()
    df = df.drop(index=skipped_rows)

    if len(df) == 0:
        return Response({"error": "No usable rows found in CSV after dropping empty rows."}, status=400)

    if len(df) > settings.BATCH_MAX_ROWS:
        return Response(
            {
                "error": f"CSV has {len(df)} usable rows, exceeding the max of "
                f"{settings.BATCH_MAX_ROWS}. Please split it into smaller files."
            },
            status=400,
        )

    texts = df["text"].astype(str).tolist()
    too_long = [i for i, t in zip(df.index.tolist(), texts) if len(t) > settings.MAX_TEXT_CHARS]
    if too_long:
        return Response(
            {"error": f"Row(s) {too_long[:10]} exceed the {settings.MAX_TEXT_CHARS}-character limit."},
            status=400,
        )
    row_indices = df.index.tolist()
    cost = cost_for("predict", _families(keys)) * len(texts)

    outcome, error = _charge_and_run(request, cost, lambda: registry.predict_batch(texts, keys))
    if error:
        return error
    per_model_results, status = outcome
    timings = {
        f"{model_key}_total_ms": sum(r["inference_ms"] for r in model_results)
        for model_key, model_results in per_model_results.items()
    }

    rows = []
    for i, (row_index, text) in enumerate(zip(row_indices, texts)):
        rows.append(
            {
                "row_index": int(row_index),
                "text": text,
                "text_preview": text[:120],
                "results": {model_key: model_results[i] for model_key, model_results in per_model_results.items()},
            }
        )

    return Response(
        {
            "row_count": len(rows),
            "columns_used": {"text_column": "text"},
            "timings": timings,
            "skipped_rows": skipped_rows,
            "rows": rows,
            "cost": cost,
            "quota": status,
        }
    )
