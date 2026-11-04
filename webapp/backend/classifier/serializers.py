from rest_framework import serializers


class PredictRequestSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class BatchPredictRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
