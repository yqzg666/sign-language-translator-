"""手语识别/生成 API 路由"""
from django.urls import path
from . import views

urlpatterns = [
    path("sign/generate", views.generate_sign_video, name="generate_sign_video"),
    path("sign/generate-stream", views.generate_sign_video_stream, name="generate_sign_video_stream"),
    path("sign/recognize", views.recognize_sign, name="recognize_sign"),
    path("video/translate", views.translate_video, name="translate_video"),
    path("video/translate-stream", views.translate_video_stream, name="translate_video_stream"),
    path("video/dub", views.dub_video, name="dub_video"),
    path("video/dub-audio/<str:filename>", views.serve_dub_audio, name="serve_dub_audio"),
]
