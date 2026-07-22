from django.urls import path
from .views import text_to_sign, text_to_sign_stitch

urlpatterns = [
    path("text-to-sign/", text_to_sign, name="text_to_sign"),
    path("text-to-sign/stitch/", text_to_sign_stitch, name="text_to_sign_stitch"),
]
