import time

import pandas as pd
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import BatchPredictRequestSerializer, PredictRequestSerializer
from .services.registry import registry


@api_view(["GET"])
def health(request):
    return Response({"models": registry.status()})


@api_view(["GET"])
def models(request):
    return Response({"models": registry.model_list()})


@api_view(["POST"])
def predict(request):
    serializer = PredictRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    text = serializer.validated_data["text"]

    start = time.perf_counter()
    results = registry.predict_all(text)
    total_ms = (time.perf_counter() - start) * 1000

    return Response({"input_text": text, "results": results, "total_ms": total_ms})


@api_view(["POST"])
def predict_explain(request):
    serializer = PredictRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    text = serializer.validated_data["text"]

    start = time.perf_counter()
    results = registry.explain_all(text)
    total_ms = (time.perf_counter() - start) * 1000

    return Response({"input_text": text, "results": results, "total_ms": total_ms})


@api_view(["POST"])
def predict_batch(request):
    serializer = BatchPredictRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    uploaded_file = serializer.validated_data["file"]

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
    row_indices = df.index.tolist()

    per_model_results = registry.predict_all_batch(texts)
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
        }
    )
