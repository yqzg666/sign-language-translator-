from django.urls import path
from . import views

urlpatterns = [
    path("records/", views.history, name="history_root"),
    path("records/<str:record_id>/", views.history, name="history"),
    path("materials/folders", views.material_folders, name="material_folders"),
    path("materials/folders/<int:folder_id>", views.material_folder_detail, name="material_folder_detail"),
    path("materials/", views.materials, name="materials"),
    path("materials/<int:material_id>", views.material_detail, name="material_detail"),
    path("materials/upload", views.material_upload, name="material_upload"),
    path("materials/move", views.material_move, name="material_move"),
]