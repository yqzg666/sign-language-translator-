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
    path("video/dub-v2", views.dub_video_v2, name="dub_video_v2"),
    path("video/dub-audio/<str:filename>", views.serve_dub_audio, name="serve_dub_audio"),
    # 音色管理
    path("voice/reference", views.upload_voice_reference, name="upload_voice_reference"),
    path("voice/references", views.list_voice_references, name="list_voice_references"),
    path("voice/references/<str:voice_name>", views.delete_voice_reference, name="delete_voice_reference"),
    path("voice/audio/<str:voice_name>/<str:filename>", views.serve_voice_audio, name="serve_voice_audio"),
]
