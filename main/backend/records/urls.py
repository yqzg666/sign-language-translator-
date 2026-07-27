from django.urls import path, re_path
from .views import history

urlpatterns = [
    path("records/", history),
    re_path(r"^records/(stt:\d+|tts:\d+)/$", history),
]
