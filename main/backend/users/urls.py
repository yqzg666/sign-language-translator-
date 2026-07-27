"""用户鉴权路由"""
from django.urls import path
from . import views

urlpatterns = [
    path("auth/login", views.login, name="login"),
    path("auth/register", views.register, name="register"),
    path("auth/logout", views.logout, name="logout"),
    path("auth/verify", views.verify_token, name="verify_token"),
    path("user/profile", views.get_profile, name="get_profile"),
    path("user/password", views.change_password, name="change_password"),
    path("user/account", views.delete_account, name="delete_account"),
]
