"""聊天路由"""
from django.urls import path
from . import views

urlpatterns = [
    path("chat/message", views.chat, name="chat"),
    path("chat/extract-sign", views.extract_sign, name="extract_sign"),
    path("chat/speech-to-text", views.speech_to_text, name="speech_to_text"),
]
