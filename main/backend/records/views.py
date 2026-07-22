"""翻译记录 CRUD API — 统一查询/删除（合并两种记录类型）"""
import math
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import TranslationRecord
from text_to_sign.models import TextToSignRecord

DATASET_PREFIXES = ("train-", "dev-", "test-")


def _video_url_from_name(video_name):
    """根据视频文件名尝试构造可访问的 URL"""
    name = video_name or ""
    if any(name.startswith(p) for p in DATASET_PREFIXES):
        subset = name.split("-")[0]
        return f"/video/{subset}/A/{name}"
    return ""


def _all_records():
    """合并两种记录类型并按时间倒序"""
    items = []
    for r in TranslationRecord.objects.all():
        items.append({
            "id": f"stt:{r.id}",
            "type": "手语→文本",
            "input": r.chinese_text or "",
            "detail": r.gloss_text or "",
            "video_name": r.video_name or "",
            "video_url": _video_url_from_name(r.video_name),
            "created_at": r.created_at.isoformat()[:19],
        })
    for r in TextToSignRecord.objects.all():
        video_url = f"/video/generated/A/{r.video_name}" if r.method == "stitch" else _video_url_from_name(r.video_name)
        items.append({
            "id": f"tts:{r.id}",
            "type": "文本→手语",
            "input": r.input_text or "",
            "detail": r.matched_text or r.matched_gloss or "",
            "video_name": r.video_name or "",
            "video_url": video_url,
            "created_at": r.created_at.isoformat()[:19],
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


@api_view(["GET", "POST", "DELETE"])
def history(request, record_id=None):
    """
    统一的翻译记录接口

    GET   /api/records/                       → 分页列表
          /api/records/?id=tts:5              → 单条查询
          /api/records/?page=1&page_size=20   → 指定页

    POST  /api/records/                       → 创建手语→文本记录

    DELETE /api/records/                      → body: {"action": "delete_all"} 一键清空
           /api/records/<id>/                 → 删除单条
    """
    # ===== 创建记录 =====
    if request.method == "POST":
        data = request.data
        record = TranslationRecord.objects.create(
            video_name=data.get("video_name", ""),
            gloss_text=data.get("gloss_text", ""),
            chinese_text=data.get("chinese_text", ""),
        )
        return Response({
            "id": record.id,
            "video_name": record.video_name,
            "gloss_text": record.gloss_text,
            "chinese_text": record.chinese_text,
            "created_at": record.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)

    # ===== 删除 =====
    if request.method == "DELETE":
        # 一键清空
        data = getattr(request, "data", {})
        if data and data.get("action") == "delete_all":
            cnt_stt = TranslationRecord.objects.all().delete()[0]
            cnt_tts = TextToSignRecord.objects.all().delete()[0]
            return Response({"deleted": cnt_stt + cnt_tts}, status=status.HTTP_200_OK)

        # 单条删除
        if record_id is None:
            return Response({"error": "缺少记录 ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            model_type, real_id = record_id.split(":")
            real_id = int(real_id)
        except (ValueError, AttributeError):
            return Response({"error": "无效的记录 ID 格式"}, status=status.HTTP_400_BAD_REQUEST)

        if model_type == "stt":
            try:
                TranslationRecord.objects.get(id=real_id).delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except TranslationRecord.DoesNotExist:
                return Response({"error": "记录不存在"}, status=status.HTTP_404_NOT_FOUND)
        elif model_type == "tts":
            try:
                TextToSignRecord.objects.get(id=real_id).delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except TextToSignRecord.DoesNotExist:
                return Response({"error": "记录不存在"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"error": "未知的记录类型"}, status=status.HTTP_400_BAD_REQUEST)

    # ===== 查询 =====
    items = _all_records()

    # 单条查询
    single_id = request.query_params.get("id")
    if single_id:
        for item in items:
            if item["id"] == single_id:
                return Response(item)
        return Response({"error": "记录不存在"}, status=status.HTTP_404_NOT_FOUND)

    # 分页
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 20))
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": page_items,
    })
