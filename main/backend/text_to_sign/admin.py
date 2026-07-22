from django.contrib import admin
from .models import TextToSignRecord


@admin.register(TextToSignRecord)
class TextToSignRecordAdmin(admin.ModelAdmin):
    list_display = ["input_text", "matched_text", "method", "similarity", "video_name", "created_at"]
    search_fields = ["input_text", "matched_text"]
