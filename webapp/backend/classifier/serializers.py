from django.conf import settings
from rest_framework import serializers

from .services.registry import registry


class ModelSelectionMixin:
    """Validates the `models` list: at least one key, every key loaded, and
    (for explain) every key's family supports explanation. Duplicates are
    dropped, keeping the caller's order."""

    action = "predict"

    def validate_models(self, keys):
        keys = list(dict.fromkeys(keys))
        unknown = [k for k in keys if not registry.is_loaded(k)]
        if unknown:
            raise serializers.ValidationError(f"Unknown or unavailable model(s): {', '.join(unknown)}")
        if self.action == "explain":
            unsupported = [k for k in keys if registry.family_of(k) not in settings.QUOTA_COSTS["explain"]]
            if unsupported:
                raise serializers.ValidationError(
                    f"Explanation is not available for: {', '.join(unsupported)}"
                )
        return keys


class PredictRequestSerializer(ModelSelectionMixin, serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)
    models = serializers.ListField(child=serializers.CharField(), allow_empty=False)

    def validate_text(self, text):
        if len(text) > settings.MAX_TEXT_CHARS:
            raise serializers.ValidationError(
                f"Text is {len(text)} characters; the maximum is {settings.MAX_TEXT_CHARS}."
            )
        return text


class ExplainRequestSerializer(PredictRequestSerializer):
    action = "explain"


class BatchPredictRequestSerializer(ModelSelectionMixin, serializers.Serializer):
    file = serializers.FileField()
    # Multipart form: send one `models` field per selected key.
    models = serializers.ListField(child=serializers.CharField(), allow_empty=False)
