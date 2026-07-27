"""
文本→手语 API — 混合检索 + DeepSeek 二次确认 + 视频拼接兜底
1. 句向量检索 → DeepSeek 语义确认
2. DeepSeek 改写后再次检索
3. Gloss 序列匹配兜底
4. 视频拼接（当以上均失败时）
5. 统一视频直出接口
"""
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

import cv2
import numpy as np
import torch

from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import TextToSignRecord
from .serializers import TextToSignRecordSerializer
from .sentence_index import SentenceSearcher, _find_best_match_by_gloss, find_video_by_gloss_word, _load_records


# ============ 配置 ============

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

SIMILARITY_THRESHOLD = 0.75      # 阶段1 直接命中
DEEPSEEK_THRESHOLD = 0.65        # 改写后命中
SIMILARITY_TOP_K = 10

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # main/
VIDEO_BASE = BASE_DIR / "data" / "video"


# ============ 视频直出 ============

def serve_video(request, subset, translator, video_id):
    """通过 /video/<subset>/<translator>/<video_id> 直出视频文件（支持 Range 请求）"""
    import re

    video_path = VIDEO_BASE / subset / translator / video_id
    if not video_path.exists():
        raise Http404("视频文件不存在")

    file_size = video_path.stat().st_size
    range_header = request.META.get("HTTP_RANGE", "")

    if range_header:
        match = re.search(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            length = end - start + 1

            with open(video_path, "rb") as f:
                f.seek(start)
                data = f.read(length)

            resp = HttpResponse(data, status=206, content_type="video/mp4")
            resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp["Content-Length"] = str(length)
            resp["Accept-Ranges"] = "bytes"
            resp["Cache-Control"] = "no-cache"
            resp["Access-Control-Allow-Origin"] = "*"
            return resp

    resp = FileResponse(open(video_path, "rb"), content_type="video/mp4")
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Length"] = str(file_size)
    resp["Cache-Control"] = "no-cache"
    resp["Access-Control-Allow-Origin"] = "*"
    return resp


# ============ DeepSeek 工具 ============

def _call_deepseek(prompt, system_prompt, temperature=0.3, max_tokens=256):
    """调用 DeepSeek API"""
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = Request(DEEPSEEK_API_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {DEEPSEEK_API_KEY}")

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except URLError as e:
        raise RuntimeError(f"DeepSeek API 请求失败: {e.reason}")


# ============ 构建响应 ============

def _build_video_url(record):
    """构建可直接通过 Django 访问的视频 URL"""
    subset = record["subset"]
    translator = Path(record["video_path"]).parent.name
    video_name = Path(record["video_path"]).name
    return f"/video/{subset}/{translator}/{video_name}"


def _build_response(record, score, method, note=None, input_text=""):
    """构建成功响应"""
    video_url = _build_video_url(record)

    # 保存记录
    TextToSignRecord.objects.create(
        input_text=input_text,
        matched_text=record["chinese"],
        matched_gloss=record["gloss"],
        video_name=Path(record["video_path"]).name,
        similarity=score,
        method=method,
    )

    resp_data = {
        "video_id": record["video_id"],
        "video_url": video_url,
        "chinese_text": record["chinese"],
        "gloss_text": record["gloss"],
        "similarity": round(score, 4),
        "method": method,
        "note": note or "",
    }
    return Response(resp_data, status=status.HTTP_200_OK)


# ============ DeepSeek 二次确认 ============

def _deepseek_verify_match(user_input, matched_text, score):
    """
    让 DeepSeek 判断匹配结果在语义上是否合理
    返回 (is_ok: bool, reason: str)
    """
    prompt = f"""你是一个严格的语义匹配判断专家。判断下面两个句子的语义是否真正匹配：

用户输入: {user_input}
视频库句子: {matched_text}
相似度得分: {score:.2f}

核心判断原则：两个句子是否在**实际意图**和**使用场景**上一致？
- "几点了" vs "这都几点了" → ❌ 前者是中性问时间，后者是抱怨太晚
- "多少钱" vs "怎么卖" → ✅ 都是问价格
- "你叫什么" vs "你叫什么名字" → ✅ 意思完全一致

要求：
1. 意图匹配 → ✅ 是
2. 意图不同 → ❌ 否
3. 只输出判断结果，一行

判断结果："""

    try:
        result = _call_deepseek(
            prompt,
            "你是一个严格的语义匹配专家，判断两个句子的实际意图是否一致。特别注意区分字面相似但实际意图不同的表达。",
            temperature=0.1,
            max_tokens=64,
        )
        is_ok = result.startswith("✅") or result.startswith("是") or "是" in result[:3]
        return is_ok, result
    except RuntimeError:
        # DeepSeek 调用失败时，信任向量检索结果
        return True, "DeepSeek 不可用，信任向量检索"


# ============ 主流程 ============

def _try_match(input_text, searcher, method, record, score, note_suffix=""):
    """尝试一次匹配，通过 DeepSeek 验证后返回响应"""
    # 只有原始向量检索且极高相似度 (>0.95) 才跳过验证
    if method == "retrieval" and score >= 0.95:
        return _build_response(record, score, method,
                               note=f"{note_suffix}极高命中" if note_suffix else None,
                               input_text=input_text)
    # DeepSeek 语义确认
    is_ok, reason = _deepseek_verify_match(input_text, record["chinese"], score)
    if is_ok:
        return _build_response(record, score, method,
                               note=f"DeepSeek确认通过: {reason}",
                               input_text=input_text)
    return None  # 验证不通过


@api_view(["POST"])
def text_to_sign(request):
    """
    文本 → 手语视频 四阶段混合检索

    POST body: {"text": "现在几点了"}
    """
    input_text = request.data.get("text", "").strip()
    if not input_text:
        return Response({"error": "请提供输入文本"}, status=status.HTTP_400_BAD_REQUEST)

    searcher = SentenceSearcher()
    try:
        searcher.load()
    except FileNotFoundError:
        return Response({"error": "句向量索引未构建"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # ====== 阶段1: 句向量检索 + DeepSeek 确认 ======
    results = searcher.search(input_text, top_k=5)
    top_record = results[0]["record"]
    top_score = results[0]["score"]

    top_rejected = False  # 记录最佳匹配是否被 DeepSeek 拒绝

    if top_score >= SIMILARITY_THRESHOLD:
        resp = _try_match(input_text, searcher, "retrieval", top_record, top_score)
        if resp:
            return resp
        top_rejected = True  # DeepSeek 拒绝了最佳匹配

    # ====== 阶段2: DeepSeek 改写再次检索 ======
    top_k_results = results  # 已经查过了
    candidates_text = "\n".join(
        f"{i+1}. {r['record']['chinese']}"
        for i, r in enumerate(top_k_results[:5])
    )
    rewrite_prompt = f"""用户想表达以下意思，但手语视频库中没有完全匹配的句子。
请将用户输入改写成与下方候选句子风格一致的中文句子。
注意：改写后必须保留用户的**原始意图**，不要改变句子的语用功能。

用户输入: {input_text}

候选句子:
{candidates_text}

改写要求：
1. 保留用户原意的核心意思和语气（问时间→问时间，抱怨→抱怨）
2. 用更口语化、更自然的表达
3. 可以调整句式但不要改变**实际意图**
4. 输出仅改写结果，不加解释

改写结果："""

    try:
        rewritten = _call_deepseek(
            rewrite_prompt,
            "你是一个改写助手，将用户输入改写成更自然的表达，必须保留原意的语气和语用功能。",
            temperature=0.2,
        )
        if rewritten:
            rewrite_results = searcher.search(rewritten, top_k=3)
            # 先试最相似的
            for r in rewrite_results:
                if r["score"] >= DEEPSEEK_THRESHOLD:
                    resp = _try_match(input_text, searcher, "deepseek", r["record"], r["score"],
                                      note_suffix=f"改写自: {rewritten}")
                    if resp:
                        return resp
    except RuntimeError:
        pass

    # ====== 阶段3: Gloss 序列匹配兜底 ======
    gloss_prompt = f"""将以下中文句子转换为手语 Gloss 序列。

规则：
1. 用 / 分隔每个手语词汇
2. 去掉虚词（的、了、吗、把、被等）
3. 使用简短的核心词汇
4. 句末加 。

中文句子: {input_text}
Gloss 序列:"""

    try:
        gloss_result = _call_deepseek(
            gloss_prompt,
            "你是一个手语翻译助手，将中文转换为手语 Gloss 序列。",
            temperature=0.1,
            max_tokens=128,
        )
        if gloss_result:
            gloss_results = _find_best_match_by_gloss(gloss_result, top_k=3)
            for r in gloss_results:
                if r["score"] > 0.3:
                    resp = _try_match(input_text, searcher, "gloss", r["record"], r["score"])
                    if resp:
                        return resp
    except RuntimeError:
        pass

    # 全部失败 → 如果最佳匹配曾被 DeepSeek 拒绝，不能返回
    if top_rejected:
        return Response({
            "error": "未能找到在语义上匹配的手语视频",
            "input_text": input_text,
            "hint": f"最接近的句子是「{top_record['chinese']}」(相似度 {top_score:.2f})，但语义不匹配",
        }, status=status.HTTP_404_NOT_FOUND)

    if top_score > 0:
        return _build_response(top_record, top_score, "retrieval",
                               note="未找到高度匹配，返回最相近结果", input_text=input_text)

    return Response({
        "error": "未找到匹配的手语视频",
        "input_text": input_text,
    }, status=status.HTTP_404_NOT_FOUND)


# ============ TFNet 定位视频词汇 ============

# 懒加载模型（首次调用时初始化）
_LOCATOR_CACHE = {"model": None, "word2idx": None, "idx2word": None, "device": None}

def _ensure_locator():
    """懒加载 TFNet 模型（用于在视频中定位具体词汇的位置）"""
    if _LOCATOR_CACHE["model"] is not None:
        return (
            _LOCATOR_CACHE["model"],
            _LOCATOR_CACHE["word2idx"],
            _LOCATOR_CACHE["idx2word"],
            _LOCATOR_CACHE["device"],
        )

    import sys
    src_dir = str(BASE_DIR / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from inference import build_vocab, load_model

    label_dir = BASE_DIR / "data" / "label"
    word2idx, vocab_size, idx2word = build_vocab(
        [str(label_dir / "train.csv"), str(label_dir / "dev.csv"), str(label_dir / "test.csv")],
        "CE-CSL",
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint_path = BASE_DIR / "checkpoints" / "TFNet-CE-CSL-CSLDaily-32.46.pth"
    model = load_model(str(checkpoint_path), 1024, vocab_size, device, "CE-CSL")

    _LOCATOR_CACHE["model"] = model
    _LOCATOR_CACHE["word2idx"] = word2idx
    _LOCATOR_CACHE["idx2word"] = idx2word
    _LOCATOR_CACHE["device"] = device

    print(f"TFNet 定位器已加载（{device}）")
    return model, word2idx, idx2word, device


def _locate_and_clip_segment(video_path, target_word, min_frames=10):
    """
    用 TFNet 在视频中定位目标词汇的精确帧区间并裁剪

    Returns: list of RGB frames 或空列表（兜底取前 30 帧）
    """
    model, word2idx, idx2word, device = _ensure_locator()
    from inference import locate_gloss_in_video

    # 先读帧（RGB，给 locate 用）
    frames_rgb = _read_video_frames_rgb(video_path)
    if not frames_rgb:
        return []

    # 定位目标词
    loc = locate_gloss_in_video(model, video_path, target_word, word2idx, device, frames=frames_rgb)

    if loc is None or loc["end_frame"] - loc["start_frame"] < min_frames:
        # 兜底：取视频前 1/3
        n = max(min_frames, len(frames_rgb) // 3)
        return frames_rgb[:n]

    return frames_rgb[loc["start_frame"] : loc["end_frame"]]


def _read_video_frames_rgb(video_path):
    """用 OpenCV 读取视频，返回 RGB 帧列表"""
    frames = []
    cap = cv2.VideoCapture(str(video_path))
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames


def _stitch_video_segments(segments, output_path, fps=30):
    """将多个帧段拼接成一个视频文件（H.264 编码，浏览器原生播放）"""
    if not segments:
        return False

    # 统一尺寸并合并所有帧
    h, w = segments[0][0].shape[:2]
    all_frames = []
    for seg in segments:
        for frame in seg:
            if frame.shape[1] != w or frame.shape[0] != h:
                frame = cv2.resize(frame, (w, h))
            all_frames.append(frame)

    all_frames = np.stack(all_frames)

    # 使用 imageio-ffmpeg 写入 H.264 编码
    import imageio.v3 as iio3
    iio3.imwrite(
        str(output_path),
        all_frames,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
    )
    return True


@api_view(["POST"])
def text_to_sign_stitch(request):
    """
    文本 → 手语视频拼接（检索不到时使用）
    对用户输入的每个 Gloss 词，用 TFNet 定位其在视频中的精确位置并裁剪拼接
    """
    input_text = request.data.get("text", "").strip()
    if not input_text:
        return Response({"error": "请提供输入文本"}, status=status.HTTP_400_BAD_REQUEST)

    # 1. 生成 Gloss 序列
    gloss_prompt = f"""将以下中文句子转换为手语 Gloss 序列。

规则：
1. 用 / 分隔每个手语词汇
2. 去掉虚词（的、了、吗、把、被等）
3. 使用简短的核心词汇
4. 句末加 。

中文句子: {input_text}
Gloss 序列:"""

    try:
        gloss_result = _call_deepseek(
            gloss_prompt,
            "你是一个手语翻译助手，将中文转换为手语 Gloss 序列。",
            temperature=0.1,
            max_tokens=128,
        )
    except RuntimeError as e:
        return Response({"error": f"DeepSeek 调用失败: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if not gloss_result:
        return Response({"error": "无法生成手语 Gloss 序列"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 2. 对每个 Gloss 词搜索对应视频
    gloss_words = [g.strip() for g in gloss_result.rstrip("。").split("/") if g.strip()]
    if not gloss_words:
        return Response({"error": "生成的 Gloss 序列为空"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    records = _load_records()
    video_paths = []
    matched_words = []
    for word in gloss_words:
        record = find_video_by_gloss_word(word, records)
        if record and Path(record["video_path"]).exists():
            video_paths.append(record["video_path"])
            matched_words.append(word)

    if not video_paths:
        return Response({
            "error": "未找到任何匹配的手语词汇视频",
            "gloss_words": gloss_words,
        }, status=status.HTTP_404_NOT_FOUND)

    # 3. 用 TFNet 精确定位并裁剪每个词汇的片段
    segments = []
    for word, path in zip(matched_words, video_paths):
        seg = _locate_and_clip_segment(path, word)
        if seg:
            segments.append(seg)

    if len(segments) < 1:
        return Response({"error": "无法读取匹配的视频文件"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 5. 拼接输出（保留旧视频供历史记录查看）
    output_dir = VIDEO_BASE / "generated" / "A"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = input_text.replace("?", "").replace("？", "").replace(" ", "")[:20]
    output_name = f"stitch_{safe_name}_{int(time.time())}.mp4"
    output_path = output_dir / output_name

    stitched = _stitch_video_segments(segments, output_path)
    if not stitched:
        return Response({"error": "视频拼接失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 6. 返回
    video_url = f"/video/generated/A/{output_name}"
    gloss_text = " / ".join(matched_words)

    TextToSignRecord.objects.create(
        input_text=input_text,
        matched_text=input_text,
        matched_gloss=gloss_text,
        video_name=output_name,
        similarity=0.0,
        method="stitch",
    )

    return Response({
        "video_url": video_url,
        "chinese_text": input_text,
        "gloss_text": gloss_text,
        "similarity": 0.0,
        "method": "stitch",
        "note": f"已拼接 {len(segments)} 个手语词汇片段",
    })
