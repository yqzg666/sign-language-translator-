"""
用户鉴权 API — 登录/注册/注销/资料/修改密码/注销账号
使用 Django 内置 User 模型 + 数据库持久化 Token
"""
import hashlib
import time
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import AuthToken


def _generate_token(username):
    """生成唯一的 token"""
    raw = f"{username}:{time.time()}:{hashlib.sha256(username.encode()).hexdigest()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _create_token(user):
    """生成并持久化 token"""
    for _ in range(3):  # 防碰撞重试
        token = _generate_token(user.username)
        if not AuthToken.objects.filter(token=token).exists():
            AuthToken.objects.create(user=user, token=token)
            return token
    # 极端情况：加时间戳再试
    token = _generate_token(f"{user.username}:{time.time_ns()}")
    AuthToken.objects.create(user=user, token=token)
    return token


def _get_user_from_request(request):
    """从请求头解析 token 并返回 User 对象"""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    token_str = auth_header.replace("Bearer ", "") if auth_header else ""
    if not token_str:
        return None
    try:
        token = AuthToken.objects.select_related("user").get(token=token_str)
        return token.user
    except AuthToken.DoesNotExist:
        return None


@api_view(["POST"])
def login(request):
    """登录 POST /api/auth/login  { account, password } → { token, user }"""
    account = request.data.get("account", "").strip()
    password = request.data.get("password", "")

    if not account:
        return Response({"error": "请输入账号"}, status=status.HTTP_400_BAD_REQUEST)
    if not password:
        return Response({"error": "请输入密码"}, status=status.HTTP_400_BAD_REQUEST)
    if len(password) < 6:
        return Response({"error": "密码错误"}, status=status.HTTP_401_UNAUTHORIZED)

    user = authenticate(username=account, password=password)
    if user is None:
        return Response({"error": "账号或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)

    token = _create_token(user)

    return Response({
        "token": token,
        "user": {
            "account": user.username,
            "nickname": user.first_name or user.username,
        }
    })


@api_view(["POST"])
def register(request):
    """注册 POST /api/auth/register  { account, password } → { success }"""
    account = request.data.get("account", "").strip()
    password = request.data.get("password", "")

    if not account:
        return Response({"error": "请输入账号"}, status=status.HTTP_400_BAD_REQUEST)
    if len(account) < 2:
        return Response({"error": "账号至少 2 个字符"}, status=status.HTTP_400_BAD_REQUEST)
    if not password:
        return Response({"error": "请输入密码"}, status=status.HTTP_400_BAD_REQUEST)
    if len(password) < 6:
        return Response({"error": "密码至少 6 位"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=account).exists():
        return Response({"error": "账号已存在，请直接登录"}, status=status.HTTP_409_CONFLICT)

    User.objects.create_user(username=account, password=password, first_name=account)
    return Response({"success": True})


@api_view(["POST"])
def logout(request):
    """注销 POST /api/auth/logout → { success } 清除当前 token"""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    token_str = auth_header.replace("Bearer ", "") if auth_header else ""
    if token_str:
        AuthToken.objects.filter(token=token_str).delete()
    return Response({"success": True})


@api_view(["GET"])
def verify_token(request):
    """验证 token 是否有效 GET /api/auth/verify → { valid, user }"""
    user = _get_user_from_request(request)
    if not user:
        return Response({"valid": False}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({
        "valid": True,
        "user": {
            "account": user.username,
            "nickname": user.first_name or user.username,
        }
    })


@api_view(["GET", "PUT"])
def get_profile(request):
    """获取/更新用户资料
    GET  /api/user/profile → { nickname, phone }
    PUT  /api/user/profile → { nickname } → { success }
    """
    user = _get_user_from_request(request)
    if not user:
        return Response({"error": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == "PUT":
        nickname = request.data.get("nickname", "").strip()
        if not nickname:
            return Response({"error": "昵称不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        user.first_name = nickname
        user.save()
        return Response({"success": True, "nickname": nickname})

    return Response({
        "nickname": user.first_name or user.username,
        "phone": getattr(user, "phone", ""),
    })


@api_view(["PUT"])
def change_password(request):
    """修改密码 PUT /api/user/password  { oldPwd, newPwd } → { success }"""
    user = _get_user_from_request(request)
    if not user:
        return Response({"error": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

    old_pwd = request.data.get("oldPwd", "")
    new_pwd = request.data.get("newPwd", "")

    if not user.check_password(old_pwd):
        return Response({"error": "旧密码错误"}, status=status.HTTP_400_BAD_REQUEST)
    if not new_pwd:
        return Response({"error": "新密码不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    if len(new_pwd) < 6:
        return Response({"error": "新密码至少 6 位"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_pwd)
    user.save()
    return Response({"success": True})


@api_view(["DELETE"])
def delete_account(request):
    """注销账号 DELETE /api/user/account → { success }"""
    user = _get_user_from_request(request)
    if not user:
        return Response({"error": "未登录"}, status=status.HTTP_401_UNAUTHORIZED)

    # 清除该用户所有 token
    AuthToken.objects.filter(user=user).delete()
    user.delete()
    return Response({"success": True})
