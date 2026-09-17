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
        frames = extract_frames_from_video(full_path_str, drop_every=4)
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
        frames = extract_frames_from_video(video_path, drop_every=4)
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
        frames = extract_frames_from_video(video_path, drop_every=4)
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
}


def _pick_edge_voice_for_clone(voice_name):
    """
    根据克隆音色名称选择不同的 edge-tts 音色
    使得在 GPT-SoVITS 不可用的情况下，不同克隆音色听起来也有区别
    """
    edge_voices = [
        "zh-CN-XiaoxiaoNeural",   # 0 温柔女声
        "zh-CN-YunxiNeural",      # 1 阳光男声
        "zh-CN-YunjianNeural",    # 2 自信男声
        "zh-CN-XiaoyiNeural",     # 3 可爱女声
        "zh-CN-YunyangNeural",    # 4 成熟男声
        "zh-CN-XiaochenNeural",   # 5 清新女声
        "zh-CN-XiaohanNeural",    # 6 知性女声
        "zh-CN-XiaomengNeural",   # 7 活泼女声
        "zh-CN-XiaoruiNeural",    # 8 柔和女声
        "zh-CN-YunfengNeural",    # 9 深沉男声
    ]
    if not voice_name:
        return edge_voices[0]
    idx = hash(voice_name) % len(edge_voices)
    return edge_voices[idx]


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
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


# ─── 音色管理 ────────────────────────────────────────────────

import uuid as uuid_mod
from urllib.parse import quote

VOICE_REF_DIR = BASE_DIR.parent / "voice_clone_server" / "ref_audio"
CLONE_SERVER_URL = "http://127.0.0.1:9880"


@api_view(["POST"])
def upload_voice_reference(request):
    """
    上传参考音频用于音色克隆
    POST /api/voice/reference (multipart)
      audio:  音频文件（WAV/MP3）
      text:   音频对应的文本内容
      name:   音色名称（可选，自动生成）
    """
    audio_file = request.FILES.get("audio")
    text = request.data.get("text", "").strip()
    name = request.data.get("name", "").strip()

    if not audio_file:
        return Response({"error": "请上传音频文件"}, status=status.HTTP_400_BAD_REQUEST)
    if not text:
        return Response({"error": "请提供音频对应的文本内容"}, status=status.HTTP_400_BAD_REQUEST)

    if not name:
        name = f"voice_{uuid_mod.uuid4().hex[:6]}"

    # 保存音频
    voice_dir = VOICE_REF_DIR / name
    voice_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(audio_file.name).suffix or ".wav"
    audio_path = voice_dir / f"reference{ext}"
    with open(audio_path, "wb") as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    # 保存文本
    with open(voice_dir / "transcript.txt", "w", encoding="utf-8") as f:
        f.write(text)

    # 尝试通知克隆服务器
    _notify_clone_server(name)

    return Response({
        "success": True,
        "name": name,
        "ref_text": text,
    })


@api_view(["GET"])
def list_voice_references(request):
    """列出所有已保存的参考音色"""
    voices = []
    if not VOICE_REF_DIR.exists():
        return Response({"voices": []})

    for item in sorted(VOICE_REF_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not item.is_dir():
            continue
        audio_file = None
        for ext in (".wav", ".mp3", ".m4a", ".ogg", ".webm"):
            candidates = list(item.glob(f"*{ext}"))
            if candidates:
                audio_file = str(candidates[0])
                break

        transcript = ""
        transcript_file = item / "transcript.txt"
        if transcript_file.exists():
            transcript = transcript_file.read_text(encoding="utf-8").strip()

        if audio_file:
            voices.append({
                "name": item.name,
                "ref_text": transcript,
                "audio_url": f"/api/voice/audio/{item.name}/{Path(audio_file).name}",
            })

    return Response({"voices": voices})


@api_view(["GET"])
def serve_voice_audio(request, voice_name, filename):
    """提供参考音频文件"""
    audio_path = VOICE_REF_DIR / voice_name / filename
    if not audio_path.exists():
        raise Http404("音频文件不存在")

    resp = FileResponse(open(audio_path, "rb"))
    resp["Access-Control-Allow-Origin"] = "*"
    return resp


@api_view(["DELETE"])
def delete_voice_reference(request, voice_name):
    """删除指定的参考音色"""
    voice_dir = VOICE_REF_DIR / voice_name
    if not voice_dir.exists():
        return Response({"error": "音色不存在"}, status=status.HTTP_404_NOT_FOUND)

    import shutil
    shutil.rmtree(voice_dir)
    return Response({"success": True})


def _notify_clone_server(voice_name):
    """通知克隆服务器有新参考音频（可选）"""
    try:
        req = Request(
            f"{CLONE_SERVER_URL}/health",
            method="GET",
        )
        with urlopen(req, timeout=2):
            pass
    except Exception:
        pass  # 克隆服务器未启动不影响主流程


@api_view(["POST"])
def dub_video_v2(request):
    """
    配音合成 v2：支持音色克隆
    POST /api/video/dub-v2  { text, language, voice_name? }
    若 voice_name 存在且指向已上传的参考音频，使用 GPT-SoVITS 克隆该音色；
    否则回退到原版 edge-tts。
    """
    text = request.data.get("text", "").strip()
    language = request.data.get("language", "zh").strip()
    voice_name = request.data.get("voice_name", "").strip()

    if not text:
        return Response({"error": "请提供配音文本"}, status=status.HTTP_400_BAD_REQUEST)

    # 检查是否使用克隆音色
    use_clone = False
    ref_audio_path = None
    ref_text = ""

    if voice_name:
        voice_dir = VOICE_REF_DIR / voice_name
        if voice_dir.exists():
            audio_files = list(voice_dir.glob("*.*"))
            transcript_file = voice_dir / "transcript.txt"

            for f in audio_files:
                if f.suffix.lower() in (".wav", ".mp3", ".m4a"):
                    ref_audio_path = str(f)
                    break

            if transcript_file.exists():
                ref_text = transcript_file.read_text(encoding="utf-8").strip()

            if ref_audio_path and ref_text:
                use_clone = True

    import hashlib
    import time as time_mod
    import asyncio

    # 路径配置
    from django.conf import settings as dj_settings

    if use_clone:
        # ===== 使用 GPT-SoVITS 音色克隆 =====
        try:
            import requests as http_requests

            payload = {
                "ref_audio_path": ref_audio_path,
                "ref_text": ref_text,
                "target_text": text,
                "voice_name": voice_name,
            }

            resp = http_requests.post(
                f"{CLONE_SERVER_URL}/clone",
                json=payload,
                timeout=60,
            )
            import logging as _lg
            _lg.getLogger().warning(f"[dub_v2_debug] proxy status={resp.status_code}, content_type={resp.headers.get('content-type','')[:30]}, size={len(resp.content)}, body={resp.text[:200]}")
            if resp.status_code == 200:
                # 保存返回的音频
                safe = hashlib.md5((text + "clone").encode()).hexdigest()[:12]
                audio_name = f"clone_{safe}_{int(time_mod.time())}.wav"
                audio_path = DUB_DIR / audio_name

                with open(audio_path, "wb") as f:
                    f.write(resp.content)

                # 获取时长
                duration = 0
                try:
                    import soundfile as sf
                    info = sf.info(str(audio_path))
                    duration = int(info.duration)
                except Exception:
                    import subprocess as sp
                    try:
                        result = sp.run(
                            ["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1",
                             str(audio_path)],
                            capture_output=True, text=True, timeout=5,
                        )
                        duration = int(float(result.stdout.strip()))
                    except Exception:
                        pass

                audio_url = f"/api/video/dub-audio/{audio_name}"
                return Response({
                    "audio_url": audio_url,
                    "duration": duration,
                    "clone": True,
                })
        except Exception as e:
            print(f"[dub_video_v2] 克隆失败，回退 edge-tts: {e}")
            # 克隆失败，回退 edge-tts

    # ===== 回退：使用 edge-tts =====
    if use_clone and voice_name:
        # 原本要使用克隆音色但克隆失败 → 根据 voice_name 选不同的 edge-tts 音色
        voice = _pick_edge_voice_for_clone(voice_name)
    else:
        voice = _DUB_VOICES.get(language, "zh-CN-XiaoxiaoNeural")

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
            target_text = text

    safe = hashlib.md5((target_text + language).encode()).hexdigest()[:12]
    audio_name = f"dub_{safe}_{language}_{int(time_mod.time())}.mp3"
    audio_path = DUB_DIR / audio_name

    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(target_text, voice).save(str(audio_path)))
    except Exception as e:
        return Response({"error": f"语音合成失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    duration = 0
    try:
        from mutagen.mp3 import MP3
        duration = int(MP3(str(audio_path)).info.length)
    except Exception:
        pass

    audio_url = f"/api/video/dub-audio/{audio_name}"
    return Response({
        "audio_url": audio_url,
        "duration": duration,
        "clone": False,
    })


# ─── 手语斩词库（背词模块）─────────────────────────────────

def _normalize_gloss_word(word):
    """去掉 Gloss 词的数字编号后缀与标点：合适2 -> 合适；纯数字/标点/符号 -> 空"""
    import re
    w = word.strip()
    # 去末尾数字编号（合适2 -> 合适）
    w = re.sub(r"\d+$", "", w)
    # 去除常见标点（含中文破折号、连字符、斜杠、书名号、空格等）
    w = w.strip("。，？！、,.?!；;：:「」『』（）()［］[]【】《》<>-—–~～/\\_·•\u3000 ")
    # 过滤纯数字 / 空
    if not w or w.isdigit():
        return ""
    # 过滤纯符号词（不含中文或字母，如 "—" "/" "?"），避免题库出现脏选项
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", w):
        return ""
    return w


def _extract_vocab_words():
    """从 train/dev/test 的 Gloss 序列提取去重词汇，并为每个词挑选最佳对照记录。
    Returns: { norm_word: {"record":..., "raw_word":..., "score":...} }
    """
    from text_to_sign.sentence_index import _load_records

    records = _load_records()
    best = {}
    for r in records:
        gloss_words = [g.strip() for g in r["gloss"].split("/") if g.strip()]
        for pos, raw in enumerate(gloss_words):
            norm = _normalize_gloss_word(raw)
            if not norm:
                continue
            # 词位置越靠前、句子越短，该记录的对照效果越好
            score = 1.0 / (pos + 1) * (1.0 / len(gloss_words))
            cur = best.get(norm)
            if cur is None or score > cur["score"]:
                best[norm] = {"record": r, "raw_word": raw, "score": score}
    return best


def _seed_words():
    """从数据集 Gloss 提取手语词汇并写入词库（幂等）"""
    from .models import SignWord

    vocab = _extract_vocab_words()
    if not vocab:
        print("[sign_api] 数据集词汇提取为空")
        return
    existing = set(SignWord.objects.values_list("word", flat=True))
    to_add = [SignWord(word=w) for w in vocab if w not in existing]
    if to_add:
        SignWord.objects.bulk_create(to_add, ignore_conflicts=True)
    print(f"[sign_api] 已从数据集提取手语词库: {len(vocab)} 个词")


def _request_text_to_sign(text):
    """调用内部 text-to-sign 接口生成手语视频，返回 dict（video_url 等），失败抛异常"""
    import json as json_mod
    from urllib.request import Request as URLRequest, urlopen

    payload = json_mod.dumps({"text": text}).encode("utf-8")
    req = URLRequest("http://127.0.0.1:8000/api/text-to-sign/", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=60) as resp:
            return json_mod.loads(resp.read().decode("utf-8"))
    except Exception:
        # 检索失败 → 尝试视频拼接兜底
        payload2 = json_mod.dumps({"text": text, "stitch": True}).encode("utf-8")
        req2 = URLRequest("http://127.0.0.1:8000/api/text-to-sign/stitch/", data=payload2, method="POST")
        req2.add_header("Content-Type", "application/json")
        with urlopen(req2, timeout=120) as resp2:
            return json_mod.loads(resp2.read().decode("utf-8"))


def _generate_sign_description(word):
    """复用 DeepSeek（杏云同学）生成手语动作文字要领"""
    prompt = (
        f"请用简洁中文描述中国手语（CSL）中「{word}」这个词汇的手语动作要领，"
        "包括手指、手掌、手臂的动作与方向，控制在60字以内。只输出动作描述。"
    )
    system_prompt = "你是中国手语教学专家，用中文清晰描述手语动作要领，只输出动作描述。"
    try:
        return _call_deepseek(prompt, system_prompt, temperature=0.4, max_tokens=200)
    except RuntimeError:
        return ""


def _sign_word_payload(obj):
    return {
        "id": obj.id,
        "word": obj.word,
        "pinyin": obj.pinyin,
        "video_url": obj.video_url,
        "description": obj.description,
        "generated": obj.generated,
    }


@api_view(["GET"])
def list_sign_words(request):
    """手语词库列表 GET /api/vocab/list → { words: [...] }"""
    from .models import SignWord

    words = [_sign_word_payload(w) for w in SignWord.objects.all()]
    return Response({"words": words})


@api_view(["GET"])
def get_sign_word(request, pk):
    """单个词详情 GET /api/vocab/<pk>/ """
    from .models import SignWord

    try:
        obj = SignWord.objects.get(pk=pk)
    except SignWord.DoesNotExist:
        return Response({"error": "词不存在"}, status=status.HTTP_404_NOT_FOUND)
    return Response(_sign_word_payload(obj))


@api_view(["POST"])
def generate_sign_word(request, pk):
    """首次生成该词的手语视频 + 文字说明，并缓存 POST /api/vocab/<pk>/generate"""
    from .models import SignWord

    try:
        obj = SignWord.objects.get(pk=pk)
    except SignWord.DoesNotExist:
        return Response({"error": "词不存在"}, status=status.HTTP_404_NOT_FOUND)

    # 已生成：直接返回缓存
    if obj.generated and obj.video_url:
        return Response(_sign_word_payload(obj))

    # 1. 手语视频（检索/拼接，内部 HTTP 至 text-to-sign）
    video_url = ""
    try:
        result = _request_text_to_sign(obj.word)
        video_url = result.get("video_url") or result.get("videoUrl") or ""
    except Exception as exc:  # noqa: BLE001
        print(f"[sign_api] 词「{obj.word}」视频生成失败: {exc}")

    # 2. 手语动作文字说明（DeepSeek）
    if not obj.description:
        obj.description = _generate_sign_description(obj.word)

    obj.video_url = video_url
    obj.generated = True
    obj.save()

    return Response(_sign_word_payload(obj))


def _preload_vocab(limit=None):
    """为未生成视频的词，用 TFNet 从整句视频裁剪出单词语视频并打标签。
    复用 text_to_sign 的定位/裁剪/拼接能力。返回成功生成的词数。
    """
    import re
    import time as time_mod
    from .models import SignWord
    from text_to_sign.views import _locate_and_clip_segment, _stitch_video_segments, VIDEO_BASE

    vocab = _extract_vocab_words()
    qs = SignWord.objects.filter(generated=False).order_by("id")
    if limit and limit > 0:
        qs = qs[: int(limit)]

    out_dir = VIDEO_BASE / "generated" / "vocab"
    out_dir.mkdir(parents=True, exist_ok=True)

    done = 0
    total = qs.count()
    for idx, sw in enumerate(qs, 1):
        info = vocab.get(sw.word)
        if not info:
            continue  # 数据集无此词，交由 generate 接口兜底
        path = info["record"]["video_path"]
        if not os.path.exists(path):
            continue
        raw = info["raw_word"]  # 用带编号的原始词定位，命中词表更准
        try:
            seg = _locate_and_clip_segment(path, raw)
            if not seg:
                continue
            safe = re.sub(r"[^\w\u4e00-\u9fa5]", "_", sw.word)
            out_name = f"vocab_{safe}_{int(time_mod.time())}.mp4"
            out_path = out_dir / out_name
            if _stitch_video_segments([seg], out_path):
                sw.video_url = f"/video/generated/vocab/{out_name}"
                sw.generated = True
                if not sw.description:
                    sw.description = _generate_sign_description(sw.word)
                sw.save()
                done += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[sign_api] 词「{sw.word}」裁剪失败: {exc}")
        if idx % 10 == 0 or idx == total:
            print(f"[sign_api] 预加载进度: {idx}/{total}（已生成 {done}）")
    return done


# 预加载状态（供前端「扩充词库」轮询）
_PRELOAD_STATE = {"running": False, "done": 0, "limit": 0, "error": ""}


@api_view(["POST"])
def preload_sign_words(request):
    """批量预加载：后台线程用 TFNet 裁剪下一批单词语视频
    POST /api/vocab/preload  { limit } → { running, done }
    """
    try:
        limit = int(request.data.get("limit", 80) or 80)
    except (TypeError, ValueError):
        limit = 80

    if _PRELOAD_STATE["running"]:
        return Response({"running": True, "done": _PRELOAD_STATE["done"]})

    import threading
    _PRELOAD_STATE.update(running=True, done=0, limit=limit, error="")

    def run():
        try:
            _PRELOAD_STATE["done"] = _preload_vocab(limit)
        except Exception as exc:  # noqa: BLE001
            _PRELOAD_STATE["error"] = str(exc)
        finally:
            _PRELOAD_STATE["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return Response({"running": True, "done": 0})


@api_view(["GET"])
def preload_sign_words_state(request):
    """查询预加载状态 GET /api/vocab/preload-state → { running, done, limit, error }"""
    return Response({
        "running": _PRELOAD_STATE["running"],
        "done": _PRELOAD_STATE["done"],
        "limit": _PRELOAD_STATE["limit"],
        "error": _PRELOAD_STATE["error"],
    })
