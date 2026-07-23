"""
GPT-SoVITS 预训练模型下载工具
下载所需模型文件到 models/ 目录

用法:
  python download_models.py

模型文件列表:
  1. gsv-v2-final-pretrained-gpt.ckpt    (~1.2GB) - GPT 模型
  2. gsv-v2-final-pretrained-sovits.ckpt (~800MB) - SoVITS 模型
"""

import os
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# 下载源（国内自动切换镜像）
HF_BASE = "https://huggingface.co"
# 国内可用镜像（按优先级排列）
MIRRORS = [
    "https://hf-mirror.com",
]
MODEL_URLS = {
    # GPT-SoVITS v2 预训练模型（完整套件下载走 Modelscope）
    "gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt": {
        "path": MODELS_DIR / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
        "size_gb": 0.15,
    },
    "gsv-v2final-pretrained/s2G2333k.pth": {
        "path": MODELS_DIR / "gsv-v2final-pretrained" / "s2G2333k.pth",
        "size_gb": 0.1,
    },
}


# 使用 Modelscope 下载完整套件
def download_from_modelscope():
    """使用 Modelscope SDK 下载 GPT-SoVITS 预训练模型"""
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        print("  安装 modelscope: pip install modelscope")
        return False

    print("  从 Modelscope 下载 GPT-SoVITS 预训练模型套件...")
    print("  来源: AIDub/GPT-SoVITS")

    try:
        model_dir = snapshot_download(
            'AIDub/GPT-SoVITS',
            revision='master',
            cache_dir=str(MODELS_DIR / "_cache"),
            allow_patterns=["GPT_SoVITS/pretrained_models/*"],
        )
        print(f"  下载完成: {model_dir}")

        # 复制到 models/
        import shutil
        pretrained_dir = Path(model_dir) / "GPT_SoVITS" / "pretrained_models"
        if pretrained_dir.exists():
            for item in pretrained_dir.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(pretrained_dir)
                    target = MODELS_DIR / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        # 清理缓存
        cache = MODELS_DIR / "_cache"
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)

        print("  ✓ 模型文件已保存到 models/ 目录")
        return True
    except Exception as e:
        print(f"  ✗ Modelscope 下载失败: {e}")
        return False

def download_file(name, url, target_path):
    """下载单个文件，自动重试镜像源"""
    import requests

    if target_path.exists():
        size_mb = target_path.stat().st_size / 1024 / 1024
        print(f"  ✓ {name} 已存在 ({size_mb:.0f} MB)")
        return True

    # 构建尝试 URL 列表：先原地址，再镜像
    urls_to_try = [url]
    for mirror in MIRRORS:
        urls_to_try.append(url.replace(HF_BASE, mirror))

    last_error = None
    for try_url in urls_to_try:
        source = "原站" if try_url == url else f"镜像({try_url})"
        print(f"  ↓ 从{source}下载 {name}...")
        print(f"    目标: {target_path}")

        try:
            r = requests.get(try_url, stream=True, timeout=60)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            last_pct = -1

            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        if pct != last_pct:
                            print(f"    {pct}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)")
                            last_pct = pct

            print(f"  ✓ {name} 下载完成")
            return True
        except Exception as e:
            print(f"  ✗ {source} 失败: {e}")
            last_error = e
            # 清理可能残留的临时文件
            if target_path.exists():
                target_path.unlink()
            continue

    print(f"  ✗ {name} 所有下载源均失败")
    return False


def main():
    print("=" * 50)
    print("GPT-SoVITS 预训练模型下载工具")
    print("=" * 50)

    total_gb = sum(m["size_gb"] for m in MODEL_URLS.values())
    print(f"\n需要下载 {len(MODEL_URLS)} 个文件，共约 {total_gb:.1f} GB")
    print(f"保存目录: {MODELS_DIR}\n")

    # 先尝试使用 Modelscope 下载完整套件
    print("[方式1] 通过 Modelscope SDK 下载...")
    if download_from_modelscope():
        print("\n✓ 所有模型下载完成！")
        print(f"\n模型目录: {MODELS_DIR}")
        return

    # 如果 Modelscope 失败，尝试单个文件（HuggingFace + 镜像）
    print("\n[方式2] 尝试从 HuggingFace 下载单个文件...")
    total_gb = sum(m["size_gb"] for m in MODEL_URLS.values())
    try:
        import shutil
        free_gb = shutil.disk_usage(MODELS_DIR).free / 1024**3
        if free_gb < total_gb + 2:
            print(f"⚠ 警告: 磁盘空间不足 (可用 {free_gb:.1f} GB，需要 {total_gb + 2:.1f} GB)")
            cont = input("是否继续? (y/n): ")
            if cont.lower() != "y":
                print("已取消")
                return
    except Exception:
        pass

    success = True
    for name, info in MODEL_URLS.items():
        target = info["path"]  # 使用 path 字段
        if not download_file(name, "", target):
            success = False

    print()
    if success:
        print("✓ 所有模型下载完成！")
    else:
        print("⚠ 部分模型下载失败，请重试或手动下载。")
        print("手动下载地址:")
        for name, info in MODEL_URLS.items():
            print(f"  {info['url']}")

    print(f"\n模型目录: {MODELS_DIR}")


if __name__ == "__main__":
    main()
