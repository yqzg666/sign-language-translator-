from rest_framework import serializers
from .models import TranslationRecord


class TranslationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslationRecord
        fields = ["id", "video_name", "gloss_text", "chinese_text", "created_at"]
        read_only_fields = ["id", "created_at"]
