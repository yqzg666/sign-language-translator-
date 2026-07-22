from django.contrib import admin
from .models import TranslationRecord


@admin.register(TranslationRecord)
class TranslationRecordAdmin(admin.ModelAdmin):
    list_display = ["video_name", "gloss_text", "chinese_text", "created_at"]
    search_fields = ["video_name", "gloss_text", "chinese_text"]
