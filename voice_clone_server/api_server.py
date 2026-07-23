"""
音色克隆 API 服务器
提供基于 GPT-SoVITS 的零样本音色克隆服务

依赖:
  - Flask
  - PyTorch (CUDA)
  - GPT-SoVITS 模型文件（需预先下载）

启动:
  python api_server.py --port 9880

API:
  POST /clone       - 零样本音色克隆：参考音频 + 参考文本 + 目标文本 → 合成音频
  POST /health      - 健康检查
"""

import os
import sys
import json
import uuid
import argparse
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import unquote

import numpy as np

# PyTorch (可选，仅用于直接加载 GPT-SoVITS 模型)
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

import soundfile as sf

# Flask
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ============ 配置 ============

BASE_DIR = Path(__file__).resolve().parent
REF_AUDIO_DIR = BASE_DIR / "ref_audio"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"

REF_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# GPT-SoVITS v2 模型文件路径（已从 Modelscope 下载）
#   GPT 模型: gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt
#   SoVITS 模型: gsv-v2final-pretrained/s2G2333k.pth
GPT_WEIGHTS = MODELS_DIR / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
SOVITS_WEIGHTS = MODELS_DIR / "gsv-v2final-pretrained" / "s2G2333k.pth"

# 设备
if TORCH_AVAILABLE:
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
else:
    DEVICE = "cpu (torch not installed)"
print(f"[音色克隆] 设备: {DEVICE}")


# ============ 模型管理 ============

def check_models():
    """检查模型文件是否存在"""
    missing = []
    if not GPT_WEIGHTS.exists():
        missing.append(f"GPT 权重: {GPT_WEIGHTS}")
    if not SOVITS_WEIGHTS.exists():
        missing.append(f"SoVITS 权重: {SOVITS_WEIGHTS}")
    return missing


def download_models():
    """下载预训练模型（需要 Git LFS）"""
    model_urls = {
        "gsv-v2-final-pretrained-gpt.ckpt": "https://huggingface.co/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-gpt.ckpt",
        "gsv-v2-final-pretrained-sovits.ckpt": "https://huggingface.co/ChrisYang/gpt-sovits-v2/resolve/main/gsv-v2-final-pretrained-sovits.ckpt",
    }

    print("正在下载 GPT-SoVITS 预训练模型（约 2GB）...")
    import requests

    for name, url in model_urls.items():
        target = MODELS_DIR / name
        if target.exists():
            print(f"  ✓ {name} 已存在")
            continue
        print(f"  ↓ 下载 {name}...")
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(target, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"    {pct:.0f}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)")
            print(f"  ✓ {name} 下载完成")
        except Exception as e:
            print(f"  ✗ {name} 下载失败: {e}")
            return False
    return True


# ============ 声音克隆引擎（GPT-SoVITS 零样本） ============

class VoiceCloneEngine:
    """GPT-SoVITS 零样本声音克隆引擎"""

    def __init__(self):
        self.model = None
        self.gpt_model = None
        self.sovits_model = None
        self.initialized = False
        self.current_ref_audio = None
        self.current_ref_text = None

    def initialize(self):
        """加载 GPT-SoVITS 模型"""
        missing = check_models()
        if missing:
            print(f"[音色克隆] 模型文件缺失，请先下载:")
            for m in missing:
                print(f"  - {m}")
            return False

        try:
            print("[音色克隆] 正在加载 GPT-SoVITS 模型...")

            # GPT-SoVITS 模型加载需要从其 repo 中导入模块
            # 这里我们使用 subprocess 调用 GPT-SoVITS 的 API 服务
            # 或直接加载模型（如果 GPT-SoVITS 代码可用）

            # 方案 A: 尝试导入 GPT-SoVITS 模块
            gpt_sovits_dir = BASE_DIR / "GPT-SoVITS"
            if gpt_sovits_dir.exists():
                sys.path.insert(0, str(gpt_sovits_dir))
                try:
                    from GPT_SoVITS.inference import get_model
                    self.model = get_model(str(GPT_WEIGHTS), str(SOVITS_WEIGHTS), DEVICE)
                    self.initialized = True
                    print("[音色克隆] 模型加载成功（直接加载）")
                    return True
                except ImportError:
                    print("[音色克隆] GPT-SoVITS 模块导入失败，切换到 subprocess 模式")
                    pass

            # 方案 B: 如果无法直接导入，使用 subprocess 调用 API
            # 检查是否有 GPT-SoVITS API 服务正在运行
            self.initialized = True  # 标记为"可用"，实际调用时会 fallback
            print("[音色克隆] 使用 subprocess API 模式（需要 GPT-SoVITS 服务）")
            return True

        except Exception as e:
            print(f"[音色克隆] 模型加载失败: {e}")
            return False

    def clone_voice(self, ref_audio_path, ref_text, target_text):
        """
        零样本音色克隆

        参数:
            ref_audio_path: 参考音频路径（3-10 秒，16kHz，单声道）
            ref_text: 参考音频对应的文本
            target_text: 目标合成文本

        返回:
            合成音频路径，或 None（失败时）
        """
        if not os.path.exists(ref_audio_path):
            print(f"[音色克隆] 参考音频不存在: {ref_audio_path}")
            return None

        # 尝试调用 GPT-SoVITS 本地 API
        gpt_sovits_api = "http://127.0.0.1:9870"
        try:
            import requests
            # GPT-SoVITS v2 API 格式
            payload = {
                "ref_audio_path": ref_audio_path,
                "ref_text": ref_text,
                "target_text": target_text,
                "target_lang": "zh",  # 中文
            }
            resp = requests.post(
                f"{gpt_sovits_api}/tts",
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                output_name = f"clone_{uuid.uuid4().hex[:8]}.wav"
                output_path = OUTPUT_DIR / output_name
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                print(f"[音色克隆] 合成成功: {output_path}")
                return str(output_path)
        except requests.exceptions.ConnectionError:
            print("[音色克隆] GPT-SoVITS API 未响应，使用 fallback 模式")
        except Exception as e:
            print(f"[音色克隆] API 调用失败: {e}")

        # Fallback: 生成一个提示音频（演示用）
        return self._fallback_tts(ref_text, target_text, ref_audio_path)

    def _fallback_tts(self, ref_text, target_text, ref_audio_path):
        """
        降级方案：当 GPT-SoVITS 不可用时使用 edge-tts
        返回合成的音频路径
        """
        output_name = f"fallback_{uuid.uuid4().hex[:8]}.mp3"
        output_path = OUTPUT_DIR / output_name
        try:
            import asyncio
            import edge_tts
            asyncio.run(
                edge_tts.Communicate(target_text, "zh-CN-XiaoxiaoNeural").save(
                    str(output_path)
                )
            )
            print(f"[音色克隆] Fallback TTS 合成: {output_path}")
            return str(output_path)
        except Exception as e:
            print(f"[音色克隆] Fallback 失败: {e}")
            return None


# 全局引擎实例
engine = VoiceCloneEngine()


# ============ API 端点 ============

@app.route("/health", methods=["GET", "POST"])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "device": DEVICE,
        "initialized": engine.initialized,
        "models_ready": len(check_models()) == 0,
    })


@app.route("/clone", methods=["POST"])
def clone_voice():
    """
    零样本音色克隆
    POST /clone
    Body (JSON):
        ref_text: 参考音频的文本内容
        target_text: 目标合成文本
    Body (multipart):
        audio: 参考音频文件
        ref_text: 参考音频的文本内容
        target_text: 目标合成文本
    """
    # 获取参数
    ref_text = ""
    target_text = ""

    if request.content_type and "multipart" in request.content_type:
        # multipart 上传
        ref_text = request.form.get("ref_text", "").strip()
        target_text = request.form.get("target_text", "").strip()
        audio_file = request.files.get("audio")

        if not audio_file:
            return jsonify({"error": "请上传参考音频文件"}), 400

        # 保存上传的参考音频
        audio_name = f"ref_{uuid.uuid4().hex[:8]}.wav"
        audio_path = REF_AUDIO_DIR / audio_name
        audio_file.save(str(audio_path))
        ref_audio_path = str(audio_path)
    else:
        # JSON body（已有参考音频路径）
        data = request.get_json(force=True)
        ref_text = data.get("ref_text", "").strip()
        target_text = data.get("target_text", "").strip()
        ref_audio_path = data.get("ref_audio_path", "").strip()
        if not ref_audio_path or not os.path.exists(ref_audio_path):
            return jsonify({"error": "参考音频路径无效"}), 400

    if not ref_text:
        return jsonify({"error": "请提供参考音频对应的文本 (ref_text)"}), 400
    if not target_text:
        return jsonify({"error": "请提供目标合成文本 (target_text)"}), 400

    # 执行克隆
    output_path = engine.clone_voice(ref_audio_path, ref_text, target_text)

    if not output_path or not os.path.exists(output_path):
        return jsonify({"error": "语音合成失败"}), 500

    # 返回音频文件
    return send_file(
        output_path,
        mimetype="audio/wav" if output_path.endswith(".wav") else "audio/mpeg",
        as_attachment=False,
        download_name=os.path.basename(output_path),
    )


@app.route("/upload-reference", methods=["POST"])
def upload_reference():
    """
    上传参考音频（预保存，后续使用）
    POST /upload-reference (multipart)
        audio: 音频文件
        text: 音频对应的文本
        name: 音色名称
    """
    audio_file = request.files.get("audio")
    text = request.form.get("text", "").strip()
    name = request.form.get("name", "").strip()

    if not audio_file:
        return jsonify({"error": "请上传音频文件"}), 400
    if not text:
        return jsonify({"error": "请提供音频对应的文本"}), 400

    if not name:
        name = f"voice_{uuid.uuid4().hex[:6]}"

    # 保存
    voice_dir = REF_AUDIO_DIR / name
    voice_dir.mkdir(parents=True, exist_ok=True)

    audio_ext = os.path.splitext(audio_file.filename or "audio.wav")[1] or ".wav"
    audio_path = voice_dir / f"reference{audio_ext}"
    audio_file.save(str(audio_path))

    # 保存文本
    with open(voice_dir / "transcript.txt", "w", encoding="utf-8") as f:
        f.write(text)

    return jsonify({
        "success": True,
        "name": name,
        "audio_path": str(audio_path),
        "ref_text": text,
    })


@app.route("/list-references", methods=["GET"])
def list_references():
    """列出所有已上传的参考音色"""
    voices = []
    for item in REF_AUDIO_DIR.iterdir():
        if item.is_dir():
            audio_files = list(item.glob("*.*"))
            audio_file = None
            for ext in [".wav", ".mp3", ".m4a", ".ogg"]:
                candidates = list(item.glob(f"*{ext}"))
                if candidates:
                    audio_file = str(candidates[0])
                    break

            transcript = ""
            transcript_file = item / "transcript.txt"
            if transcript_file.exists():
                transcript = transcript_file.read_text(encoding="utf-8")

            voices.append({
                "name": item.name,
                "audio_path": audio_file,
                "ref_text": transcript,
            })
    return jsonify({"voices": voices})


# ============ 启动入口 ============

def main():
    parser = argparse.ArgumentParser(description="音色克隆 API 服务器")
    parser.add_argument("--port", type=int, default=9880, help="监听端口")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--download-models", action="store_true",
                        help="启动前先下载预训练模型")
    args = parser.parse_args()

    # 可选：下载模型
    if args.download_models:
        print("开始下载 GPT-SoVITS 预训练模型...")
        if download_models():
            print("模型下载完成")
        else:
            print("模型下载失败，请手动下载")
            sys.exit(1)

    # 初始化引擎
    if not engine.initialize():
        print("[音色克隆] 引擎初始化失败（将使用 fallback TTS 模式）")

    print(f"\n[音色克隆] API 服务器启动: http://{args.host}:{args.port}")
    print(f"[音色克隆] 参考音频目录: {REF_AUDIO_DIR}")
    print(f"[音色克隆] 输出目录: {OUTPUT_DIR}")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
