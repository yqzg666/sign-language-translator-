from rest_framework import serializers
from .models import TextToSignRecord


class TextToSignRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextToSignRecord
        fields = ["id", "input_text", "matched_text", "matched_gloss",
                   "video_name", "similarity", "method", "created_at"]
        read_only_fields = ["id", "created_at"]
