"""Django 根路由 — API + 管理后台 + 视频直出"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from text_to_sign.views import serve_video

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("records.urls")),
    path("api/", include("text_to_sign.urls")),
    path("api/", include("users.urls")),
    path("api/", include("chat.urls")),
    path("api/", include("sign_api.urls")),
    path("video/<str:subset>/<str:translator>/<str:video_id>", serve_video, name="serve_video"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
