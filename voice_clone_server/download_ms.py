"""
使用 Modelscope SDK 下载 GPT-SoVITS 预训练模型
只下载 pretrained_models 下的权重文件
"""
import os
import sys
from pathlib import Path

# 目标目录
MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 50)
print("从 Modelscope 下载 GPT-SoVITS 预训练模型")
print("=" * 50)

try:
    from modelscope.hub.snapshot_download import snapshot_download
except ImportError:
    print("请先安装 modelscope: pip install modelscope")
    sys.exit(1)

# 只下载 pretrained_models 目录
print("\n正在下载（约 2GB，视网速可能需要 5-30 分钟）...")
print("来源: AIDub/GPT-SoVITS\n")

try:
    model_dir = snapshot_download(
        'AIDub/GPT-SoVITS',
        revision='master',
        cache_dir=str(MODELS_DIR / "_cache"),
        allow_patterns=[
            "GPT_SoVITS/pretrained_models/*",
        ],
    )
    print(f"\n下载目录: {model_dir}")

    # 将模型文件复制到 models/ 目录下
    pretrained_dir = Path(model_dir) / "GPT_SoVITS" / "pretrained_models"
    if pretrained_dir.exists():
        print("\n复制模型文件到 models/ 目录...")
        for item in pretrained_dir.rglob("*"):
            if item.is_file():
                # 保留相对路径结构
                rel_path = item.relative_to(pretrained_dir)
                target = MODELS_DIR / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(item, target)
                size_mb = item.stat().st_size / 1024 / 1024
                print(f"  {rel_path} ({size_mb:.0f} MB)")

        print(f"\n✓ 模型文件已保存到: {MODELS_DIR}")
        print("\n模型文件列表:")
        for f in sorted(MODELS_DIR.rglob("*")):
            if f.is_file():
                print(f"  {f.relative_to(MODELS_DIR)}")
    else:
        print(f"\n⚠ 未找到 pretrained_models 目录")
        print(f"  路径: {pretrained_dir}")

except Exception as e:
    print(f"\n✗ 下载失败: {e}")
    print("\n请手动从以下地址下载模型文件:")
    print("  1. 打开 https://modelscope.cn/models/AIDub/GPT-SoVITS")
    print("  2. 进入 GPT_SoVITS/pretrained_models/ 目录")
    print("  3. 下载 gsv-v2final-pretrained/ 下的所有文件")
    print(f"  4. 放入 {MODELS_DIR} 目录")
    sys.exit(1)

finally:
    # 清理缓存
    cache_dir = MODELS_DIR / "_cache"
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir, ignore_errors=True)
        print("\n缓存已清理")
