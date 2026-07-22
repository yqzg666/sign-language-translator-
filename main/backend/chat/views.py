"""
杏云同学 API — 基于 DeepSeek 的 AI 手语课堂助手
POST /api/chat/message  { question, history } → { reply }
POST /api/chat/extract-sign  { reply } → { keyword }
POST /api/chat/speech-to-text  (multipart audio.wav) → { text }
"""
import json
import io
import os
import zipfile
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError
import vosk
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# DeepSeek 配置（复用 text_to_sign 的密钥）
DEEPSEEK_API_KEY = "os.environ.get("DEEPSEEK_API_KEY", "")"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def _call_deepseek(messages, temperature=0.7, max_tokens=1024):
    """调用 DeepSeek API"""
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
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


# 系统提示词：杏云同学的角色设定
SYSTEM_PROMPT = """你是「杏云同学」，一个专业且亲切的中国手语（CSL）教学助手。
你的核心能力：
1. 教授中国手语词汇和日常表达
2. 解释手语文化背景和使用场景
3. 回答关于手语学习的常见问题

回答风格：
- 亲切友好，像同学一样交流
- 用中文回答，必要时附上手语手势描述
- 涉及手语教学时，描述清晰的具体手势动作
- 保持简洁，每次回答不超过200字"""


@api_view(["POST"])
def chat(request):
    """AI 课堂对话 POST /api/chat/message  { question, history? } → { reply }"""
    question = request.data.get("question", "").strip()
    history = request.data.get("history", [])

    if not question:
        return Response({"error": "问题不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    # 构建消息列表
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 添加上文历史（取最近 10 轮）
    for msg in history[-20:]:
        role = msg.get("role", "")
        text = msg.get("text", "") or msg.get("content", "")
        if role in ("user", "ai"):
            messages.append({"role": "user" if role == "user" else "assistant", "content": text})

    # 添加当前问题（如果历史最后一条不是当前问题）
    if not messages or messages[-1].get("content") != question:
        messages.append({"role": "user", "content": question})

    try:
        reply = _call_deepseek(messages)
        return Response({"reply": reply})
    except RuntimeError as e:
        return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# 提取手语关键词的系统提示词
EXTRACT_PROMPT = """你是一个手语关键词提取专家。从一段 AI 教学回复中，提取出最核心的 1 个手语词汇。

规则：
1. 只提取最核心的 1 个手语词汇，通常是「」中引用的词，或者手势描述所对应的中文词
2. 如果回复中明显不包含手语教学内容（比如闲聊、非手语相关问题），返回空字符串
3. 只输出词汇本身，不要任何解释、引号、标点
4. 如果回复包含多个手语词汇，只输出第一个最重要的

示例：
回复：「你好」的手语是右手五指并拢、指尖朝上，从胸前向前推出
输出：你好

回复：谢谢的手语是右手伸出拇指，弯曲两下
输出：谢谢

回复：今天天气不错，适合出去玩
输出：

回复：请问「几点了」的手语怎么做？
输出：几点了

回复：我们来学一下「谢谢」和「不客气」的手语
输出：谢谢

只输出词汇本身："""


@api_view(["POST"])
def extract_sign(request):
    """
    从 AI 教学回复中提取手语关键词
    POST /api/chat/extract-sign  { reply } → { keyword }
    """
    reply = request.data.get("reply", "").strip()
    if not reply:
        return Response({"keyword": None})

    try:
        keyword = _call_deepseek(
            [{"role": "user", "content": EXTRACT_PROMPT + "\n\n回复：" + reply}],
            temperature=0.1,
            max_tokens=32,
        )
        # 清理：去掉可能的引号、标点
        keyword = keyword.strip().strip('"').strip("'").strip("「").strip("」")
        keyword = keyword if keyword else None
    except RuntimeError:
        keyword = None

    return Response({"keyword": keyword})


@api_view(["POST"])
def speech_to_text(request):
    """
    语音转文字：接收 WAV 音频文件，返回识别文本
    POST /api/chat/speech-to-text  (multipart: audio=file.wav) → { text }
    """
    audio_file = request.FILES.get("audio")
    if not audio_file:
        return Response({"error": "请上传音频文件"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        model = _get_vosk_model()
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.SetWords(False)

        wav_data = audio_file.read()
        # 跳过 44 字节 WAV 头部，只取 PCM 数据
        if len(wav_data) <= 44:
            return Response({"text": ""})
        pcm = wav_data[44:]

        rec.AcceptWaveform(pcm)
        result = json.loads(rec.Result())
        text = result.get("text", "").strip()
        return Response({"text": text})
    except Exception as e:
        return Response({"error": f"语音识别失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Vosk 离线语音识别模型（中文小模型 ~42MB）
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
_MODEL_NAME = "vosk-model-small-cn-0.22"
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
_vosk_model = None


def _get_vosk_model():
    """获取 Vosk 模型（单例），不存在则自动下载"""
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model
    model_path = os.path.join(_MODEL_DIR, _MODEL_NAME)
    if not os.path.exists(model_path):
        zip_path = model_path + ".zip"
        os.makedirs(_MODEL_DIR, exist_ok=True)
        print(f"[Vosk] 下载模型 {_MODEL_NAME} (~42MB)...")
        urlretrieve(_MODEL_URL, zip_path)
        print(f"[Vosk] 解压模型...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(_MODEL_DIR)
        os.remove(zip_path)
        print(f"[Vosk] 模型就绪")
    _vosk_model = vosk.Model(model_path)
    return _vosk_model
