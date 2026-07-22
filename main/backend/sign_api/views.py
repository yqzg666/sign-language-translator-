"""
手语识别与生成 API
- /api/sign/recognize — 手语→文本（TFNet 识别）
- /api/sign/generate — 文本→手语（检索已有 text-to-sign 接口）
- /api/video/translate — 上传视频识别手语
"""
import json
import os
import sys
import traceback
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # main/
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

# DeepSeek API
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def _call_deepseek(prompt, system_prompt, temperature=0.3, max_tokens=512):
    """调用 DeepSeek API 整理识别结果"""
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


# ============ TFNet 懒加载 ============

_MODEL_CACHE = {"model": None, "idx2word": None, "word2idx": None, "device": None}


def _ensure_model():
    """懒加载 TFNet 模型"""
    if _MODEL_CACHE["model"] is not None:
        return _MODEL_CACHE["model"], _MODEL_CACHE["idx2word"], _MODEL_CACHE["word2idx"]

    import torch
    from inference import load_model, build_vocab, extract_frames_from_video

    label_dir = BASE_DIR / "data" / "label"
    word2idx, vocab_size, idx2word = build_vocab(
        [str(label_dir / "train.csv"), str(label_dir / "dev.csv"), str(label_dir / "test.csv")],
        "CE-CSL",
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint_path = BASE_DIR / "checkpoints" / "TFNet-CE-CSL-CSLDaily-32.46.pth"
    model = load_model(str(checkpoint_path), 1024, vocab_size, device, "CE-CSL")

    _MODEL_CACHE["model"] = model
    _MODEL_CACHE["idx2word"] = idx2word
    _MODEL_CACHE["word2idx"] = word2idx
    _MODEL_CACHE["device"] = device
    return model, idx2word, word2idx


@api_view(["POST"])
def recognize_sign(request):
    """
    手语→文本识别
    POST /api/sign/recognize
    支持：
      - multipart 上传视频文件 (video 字段)
      - JSON body: { "video_path": "train-00001.mp4" }
    """
    video_file = request.FILES.get("video")
    video_path = request.data.get("video_path", "")

    if not video_file and not video_path:
        return Response({"error": "请上传视频文件或提供 video_path"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        model, idx2word, word2idx = _ensure_model()
    except Exception as e:
        return Response({"error": f"模型加载失败: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    import torch
    from inference import extract_frames_from_video, recognize_frames

    if video_file:
        # 保存上传的录制视频到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            for chunk in video_file.chunks():
                tmp.write(chunk)
            full_path_str = tmp.name
    else:
        # 查找数据集视频文件
        full_path = None
        for subset in ["train", "dev", "test"]:
            for prefix in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]:
                p = BASE_DIR / "data" / "video" / subset / prefix / video_path
                if p.exists():
                    full_path = p
                    break
            if full_path:
                break
        if not full_path or not full_path.exists():
            return Response({"error": f"视频文件不存在: {video_path}"}, status=status.HTTP_404_NOT_FOUND)
        full_path_str = str(full_path)

    try:
        print(f"[recognize_sign] 开始处理视频: {full_path_str}")
        frames = extract_frames_from_video(full_path_str)
        print(f"[recognize_sign] 提取帧数: {len(frames)}")
        gloss_list, raw_text = recognize_frames(model, frames, idx2word, _MODEL_CACHE["device"])
        gloss_text = " / ".join(word for word, _ in gloss_list) if gloss_list else raw_text

        # DeepSeek 整理为中文
        prompt = f"将以下手语 Gloss 序列整理成通顺的中文句子：\n{gloss_text}"
        system_prompt = "你是一个手语翻译专家，将 Gloss 序列整理为通顺自然的中文。只输出中文句子。"
        try:
            chinese_text = _call_deepseek(prompt, system_prompt, temperature=0.2)
        except RuntimeError:
            chinese_text = gloss_text

        return Response({
            "text": chinese_text,
            "gloss_text": gloss_text,
        })
    except Exception as e:
        traceback.print_exc()
        return Response({"error": f"识别失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if video_file and 'full_path_str' in locals():
            try:
                os.unlink(full_path_str)
            except Exception:
                pass


@api_view(["POST"])
def generate_sign_video(request):
    """
    文本→手语视频（代理到已有 text-to-sign API）
    POST /api/sign/generate  { text } → { videoUrl }
    """
    text = request.data.get("text", "").strip()
    if not text:
        return Response({"error": "请提供输入文本"}, status=status.HTTP_400_BAD_REQUEST)

    # 直接用 urllib 请求内部的 text-to-sign 接口
    import json as json_mod
    from urllib.request import Request as URLRequest, urlopen

    payload = json_mod.dumps({"text": text}).encode("utf-8")
    req = URLRequest("http://127.0.0.1:8000/api/text-to-sign/", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json_mod.loads(resp.read().decode("utf-8"))
            return Response({
                "videoUrl": result.get("video_url", ""),
                "chinese_text": result.get("chinese_text", ""),
                "gloss_text": result.get("gloss_text", ""),
                "similarity": result.get("similarity", 0),
                "method": result.get("method", ""),
            })
    except Exception as e:
        # 尝试拼接
        try:
            payload2 = json_mod.dumps({"text": text, "stitch": True}).encode("utf-8")
            req2 = URLRequest("http://127.0.0.1:8000/api/text-to-sign/stitch/", data=payload2, method="POST")
            req2.add_header("Content-Type", "application/json")
            with urlopen(req2, timeout=120) as resp2:
                result2 = json_mod.loads(resp2.read().decode("utf-8"))
                return Response({
                    "videoUrl": result2.get("video_url", ""),
                    "chinese_text": result2.get("chinese_text", ""),
                    "gloss_text": result2.get("gloss_text", ""),
                    "similarity": result2.get("similarity", 0),
                    "method": "stitch",
                })
        except Exception:
            pass
        return Response({"error": f"生成失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── 流式进度推送 ────────────────────────────────────────────────
from django.http import StreamingHttpResponse
import json as json_mod
import traceback as tb_mod

def _generate_stream(text):
    """Generator 逐阶段推送进度事件（JSON Lines）
    直接调用 text_to_sign 模块的内部函数，不走 HTTP，避免嵌套请求
    """
    def event(data):
        return (json_mod.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")

    try:
        # ── 延迟导入，避免模块级加载耗时 ──
        from text_to_sign.sentence_index import SentenceSearcher, _find_best_match_by_gloss, _load_records
        from text_to_sign.views import (
            SIMILARITY_THRESHOLD, DEEPSEEK_THRESHOLD,
            _try_match, _build_response, _call_deepseek,
        )

        yield event({"progress": 5, "status": "正在检索手语视频库..."})

        searcher = SentenceSearcher()
        searcher.load()

        yield event({"progress": 20, "status": "正在匹配语义..."})

        # ===== 阶段1: 句向量检索 + DeepSeek 确认 =====
        results = searcher.search(text, top_k=5)
        top_record = results[0]["record"]
        top_score = results[0]["score"]
        top_rejected = False

        if top_score >= SIMILARITY_THRESHOLD:
            yield event({"progress": 30, "status": "DeepSeek 语义确认中..."})
            resp = _try_match(text, searcher, "retrieval", top_record, top_score)
            if resp:
                yield event({"progress": 70, "status": "即将完成..."})
                yield event({
                    "progress": 100, "status": "完成!", "type": "result",
                    "videoUrl": resp.data.get("video_url", ""),
                    "chinese_text": resp.data.get("chinese_text", ""),
                    "gloss_text": resp.data.get("gloss_text", ""),
                    "similarity": resp.data.get("similarity", 0),
                    "method": "retrieval",
                })
                return
            top_rejected = True

        yield event({"progress": 40, "status": "尝试 DeepSeek 改写..."})

        # ===== 阶段2: DeepSeek 改写再次检索 =====
        candidates_text = "\n".join(
            f"{i+1}. {r['record']['chinese']}"
            for i, r in enumerate(results[:5])
        )
        rewrite_prompt = f"""用户想表达以下意思，但手语视频库中没有完全匹配的句子。
请将用户输入改写成与下方候选句子风格一致的中文句子。注意保留用户的**原始意图**。

用户输入: {text}

候选句子:
{candidates_text}

改写要求：
1. 保留原意和语气
2. 更口语化
3. 不要改变意图
4. 只输出改写结果

改写结果："""
        try:
            rewritten = _call_deepseek(
                rewrite_prompt,
                "改写助手：将用户输入改写成更自然的表达，保留原意。",
                temperature=0.2,
            )
            if rewritten:
                rewrite_results = searcher.search(rewritten, top_k=3)
                for r in rewrite_results:
                    if r["score"] >= DEEPSEEK_THRESHOLD:
                        resp = _try_match(text, searcher, "deepseek", r["record"], r["score"],
                                          note_suffix=f"改写自: {rewritten}")
                        if resp:
                            yield event({"progress": 70, "status": "即将完成..."})
                            yield event({
                                "progress": 100, "status": "完成!", "type": "result",
                                "videoUrl": resp.data.get("video_url", ""),
                                "chinese_text": resp.data.get("chinese_text", ""),
                                "gloss_text": resp.data.get("gloss_text", ""),
                                "similarity": resp.data.get("similarity", 0),
                                "method": "deepseek",
                            })
                            return
        except Exception:
            pass

        yield event({"progress": 55, "status": "尝试 Gloss 序列匹配..."})

        # ===== 阶段3: Gloss 序列匹配兜底 =====
        gloss_prompt = f"""将以下中文句子转换为手语 Gloss 序列。

规则：
1. 用 / 分隔每个手语词汇
2. 去掉虚词（的、了、吗、把、被等）
3. 使用简短的核心词汇
4. 句末加 。

中文句子: {text}
Gloss 序列:"""
        try:
            gloss_result = _call_deepseek(
                gloss_prompt,
                "手语翻译助手：将中文转换为手语 Gloss 序列。",
                temperature=0.1, max_tokens=128,
            )
            if gloss_result:
                gloss_results = _find_best_match_by_gloss(gloss_result, top_k=3)
                for r in gloss_results:
                    if r["score"] > 0.3:
                        resp = _try_match(text, searcher, "gloss", r["record"], r["score"])
                        if resp:
                            yield event({"progress": 70, "status": "即将完成..."})
                            yield event({
                                "progress": 100, "status": "完成!", "type": "result",
                                "videoUrl": resp.data.get("video_url", ""),
                                "chinese_text": resp.data.get("chinese_text", ""),
                                "gloss_text": resp.data.get("gloss_text", ""),
                                "similarity": resp.data.get("similarity", 0),
                                "method": "gloss",
                            })
                            return
        except Exception:
            pass

        # ===== 全部检索失败 → 拼接兜底，无近似返回 =====
        if top_rejected:
            yield event({"progress": 40, "status": "最佳匹配语义不符，正在尝试视频拼接..."})
            try:
                import json as _json_mod
                from urllib.request import Request as _URLReq, urlopen as _urlopen
                _payload = _json_mod.dumps({"text": text, "stitch": True}).encode("utf-8")
                _req = _URLReq("http://127.0.0.1:8000/api/text-to-sign/stitch/",
                              data=_payload, method="POST")
                _req.add_header("Content-Type", "application/json")
                with _urlopen(_req, timeout=120) as _resp:
                    _result = _json_mod.loads(_resp.read().decode("utf-8"))
                if _result.get("video_url"):
                    yield event({"progress": 80, "status": "即将完成..."})
                    yield event({
                        "progress": 100, "status": "完成!", "type": "result",
                        "videoUrl": _result["video_url"],
                        "chinese_text": _result.get("chinese_text", text),
                        "gloss_text": _result.get("gloss_text", ""),
                        "similarity": 0,
                        "method": "stitch",
                    })
                    return
            except Exception:
                pass
            yield event({"progress": 100, "status": "暂无手语片段", "type": "error",
                         "error": f"目前手语库中没有与「{text}」匹配的手语片段"})
            return

        # 未被拒绝但匹配度不够 → 不返回近似结果
        yield event({"progress": 100, "status": "暂无手语片段", "type": "error",
                     "error": f"目前手语库中没有与「{text}」匹配的手语片段"})
        return

    except Exception as e:
        tb_mod.print_exc()
        yield event({"progress": 100, "status": "失败", "type": "error", "error": str(e)})


@api_view(["POST"])
def generate_sign_video_stream(request):
    """
    文本→手语视频（流式进度推送）
    POST /api/sign/generate-stream  { text }  → SSE 事件流
    """
    text = request.data.get("text", "").strip()
    if not text:
        return Response({"error": "请提供输入文本"}, status=status.HTTP_400_BAD_REQUEST)

    resp = StreamingHttpResponse(
        streaming_content=_generate_stream(text),
        content_type="text/event-stream",
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@api_view(["POST"])
def translate_video(request):
    """
    上传视频识别手语（接受 multipart 或 video_path）
    POST /api/video/translate
    """
    # 支持两种方式：上传文件或提供路径
    video_file = request.FILES.get("video")
    video_path = request.data.get("video_path", "")

    if not video_file and not video_path:
        return Response({"error": "请上传视频文件或提供 video_path"}, status=status.HTTP_400_BAD_REQUEST)

    if video_file:
        # 保存上传的文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in video_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        video_path = tmp_path

    try:
        model, idx2word, word2idx = _ensure_model()
    except Exception as e:
        return Response({"error": f"模型加载失败: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    import torch
    from inference import extract_frames_from_video, recognize_frames

    try:
        frames = extract_frames_from_video(video_path)
        gloss_list, raw_text = recognize_frames(model, frames, idx2word, _MODEL_CACHE["device"])
        gloss_text = " / ".join(word for word, _ in gloss_list) if gloss_list else raw_text

        prompt = f"将以下手语 Gloss 序列整理成通顺的中文句子：\n{gloss_text}"
        system_prompt = "你是一个手语翻译专家，将 Gloss 序列整理为通顺自然的中文。只输出中文句子。"
        try:
            chinese_text = _call_deepseek(prompt, system_prompt, temperature=0.2)
        except RuntimeError:
            chinese_text = gloss_text

        return Response({
            "translation": chinese_text,
            "gloss_text": gloss_text,
        })
    except Exception as e:
        return Response({"error": f"识别失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        # 清理临时文件
        if video_file and 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ─── 流式翻译进度 ────────────────────────────────────────────

def _translate_stream(request):
    """Generator 逐阶段推送翻译进度"""
    import json as _json
    import tempfile
    import traceback as _tb
    import concurrent.futures
    import time

    def event(data):
        return (_json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")

    video_file = request.FILES.get("video")
    video_path = request.data.get("video_path", "")
    if not video_file and not video_path:
        yield event({"progress": 100, "type": "error", "error": "请上传视频文件或提供 video_path"})
        return

    tmp_path = None
    if video_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in video_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        video_path = tmp_path

    try:
        yield event({"progress": 5, "status": "正在加载模型..."})
        model, idx2word, word2idx = _ensure_model()

        from inference import extract_frames_from_video, recognize_frames

        yield event({"progress": 20, "status": "正在提取视频帧..."})
        frames = extract_frames_from_video(video_path)
        total_frames = len(frames)

        yield event({"progress": 35, "status": f"TFNet 识别手语中（{total_frames} 帧）..."})

        # 在后台线程跑 recognize_frames，主线程能持续推送进度
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(recognize_frames, model, frames, idx2word, _MODEL_CACHE["device"])

        # 轮询等待，期间每 2 秒发一次进度更新
        last_status = None
        while not future.done():
            time.sleep(2)
            # 计算已等待时间，给用户反馈
            status = f"TFNet 识别手语中（{total_frames} 帧），请稍候..."
            if status != last_status:
                last_status = status
                yield event({"progress": 35, "status": status})

        gloss_list, raw_text = future.result()
        executor.shutdown()
        gloss_text = " / ".join(word for word, _ in gloss_list) if gloss_list else raw_text

        yield event({"progress": 75, "status": "DeepSeek 整理结果中..."})
        prompt = f"将以下手语 Gloss 序列整理成通顺的中文句子：\n{gloss_text}"
        system_prompt = "你是一个手语翻译专家，将 Gloss 序列整理为通顺自然的中文。只输出中文句子。"
        try:
            chinese_text = _call_deepseek(prompt, system_prompt, temperature=0.2)
        except RuntimeError:
            chinese_text = gloss_text

        yield event({"progress": 95, "status": "即将完成..."})
        yield event({
            "progress": 100, "status": "完成!", "type": "result",
            "translation": chinese_text,
            "gloss_text": gloss_text,
        })
    except Exception as e:
        _tb.print_exc()
        yield event({"progress": 100, "type": "error", "error": f"识别失败: {str(e)}"})
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@api_view(["POST"])
def translate_video_stream(request):
    """
    上传视频识别手语（流式进度推送）
    POST /api/video/translate-stream  (multipart) → SSE 事件流
    """
    resp = StreamingHttpResponse(
        streaming_content=_translate_stream(request),
        content_type="text/event-stream",
    )
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


# ─── 配音生成 ────────────────────────────────────────────────

DUB_DIR = BASE_DIR / "data" / "video" / "dub"
os.makedirs(DUB_DIR, exist_ok=True)

# edge-tts 声音映射
_DUB_VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-AriaNeural",
    "yue": "zh-HK-HiuGaaiNeural",  # 粤语
    "ja": "ja-JP-NanamiNeural",
}


@api_view(["POST"])
def dub_video(request):
    """
    配音合成：文本 → TTS 音频
    POST /api/video/dub  { text, language, voice? }  →  { audio_url, duration }
    """
    text = request.data.get("text", "").strip()
    language = request.data.get("language", "zh").strip()
    if not text:
        return Response({"error": "请提供配音文本"}, status=status.HTTP_400_BAD_REQUEST)

    # 忽略前端的 voice（那是语音库的声音名，不是 edge-tts 的），
    # 始终根据语言选择对应的 edge-tts 声音
    voice = _DUB_VOICES.get(language, "zh-CN-XiaoxiaoNeural")

    import hashlib
    import time as time_mod
    import asyncio
    import edge_tts

    # 跨语言翻译
    target_text = text
    if language != "zh":
        lang_names = {"en": "英文", "yue": "粤语", "ja": "日语"}
        lang_label = lang_names.get(language, language)
        translate_prompt = f"将以下中文翻译成{lang_label}，只输出翻译结果：\n{text}"
        try:
            target_text = _call_deepseek(
                translate_prompt,
                f"翻译助手：将中文翻译成{lang_label}，只输出翻译结果。",
                temperature=0.2, max_tokens=256,
            )
        except RuntimeError:
            target_text = text  # 翻译失败则用原文

    # 生成文件名
    safe = hashlib.md5((target_text + language).encode()).hexdigest()[:12]
    audio_name = f"dub_{safe}_{language}_{int(time_mod.time())}.mp3"
    audio_path = DUB_DIR / audio_name

    try:
        asyncio.run(edge_tts.Communicate(target_text, voice).save(str(audio_path)))
    except Exception as e:
        return Response({"error": f"语音合成失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 获取音频时长
    duration = 0
    try:
        from mutagen.mp3 import MP3
        duration = int(MP3(str(audio_path)).info.length)
    except Exception:
        pass

    audio_url = f"/api/video/dub-audio/{audio_name}"
    return Response({"audio_url": audio_url, "duration": duration})


@api_view(["GET"])
def serve_dub_audio(request, filename):
    """提供配音音频文件"""
    import re
    from django.http import Http404, HttpResponse

    audio_path = DUB_DIR / filename
    if not audio_path.exists():
        raise Http404("配音文件不存在")

    file_size = audio_path.stat().st_size
    range_header = request.META.get("HTTP_RANGE", "")

    if range_header:
        match = re.search(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            length = end - start + 1
            with open(audio_path, "rb") as f:
                f.seek(start)
                data = f.read(length)
            resp = HttpResponse(data, status=206, content_type="audio/mpeg")
            resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp["Content-Length"] = str(length)
            resp["Accept-Ranges"] = "bytes"
            resp["Access-Control-Allow-Origin"] = "*"
            return resp

    # 不支持 Range 请求或不符合条件时，直接返回全部数据
    with open(audio_path, "rb") as f:
        data = f.read()
    resp = HttpResponse(data, content_type="audio/mpeg")
    resp["Content-Length"] = str(file_size)
    resp["Access-Control-Allow-Origin"] = "*"
    return resp
