from django.db import models
from django.conf import settings


class AuthToken(models.Model):
    """持久化的用户 Token"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    token = models.CharField(max_length=256, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "users"
