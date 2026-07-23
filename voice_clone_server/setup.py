"""
音色克隆服务安装脚本
完成: 虚拟环境创建、依赖安装、模型下载

用法:
  python setup.py        # 自动安装所有依赖
  python setup.py --skip-models  # 跳过模型下载（只装依赖）
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"


def run_cmd(cmd, cwd=None, desc=""):
    """运行命令并输出"""
    if desc:
        print(f"\n[{desc}]")
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or BASE_DIR, shell=True)
    if result.returncode != 0:
        print(f"  ✗ 命令失败 (exit code {result.returncode})")
        return False
    return True


def setup_venv():
    """创建虚拟环境"""
    print("\n" + "=" * 50)
    print("1. 创建 Python 虚拟环境")
    print("=" * 50)

    if VENV_DIR.exists():
        print(f"  ✓ 虚拟环境已存在: {VENV_DIR}")
        return True

    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ 创建失败: {result.stderr}")
        return False

    print(f"  ✓ 虚拟环境创建成功: {VENV_DIR}")
    return True


def get_pip():
    """获取 venv 内的 pip 路径"""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "pip")
    return str(VENV_DIR / "bin" / "pip")


def get_python():
    """获取 venv 内的 python 路径"""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python")
    return str(VENV_DIR / "bin" / "python")


def install_deps():
    """安装 Python 依赖"""
    print("\n" + "=" * 50)
    print("2. 安装 Python 依赖")
    print("=" * 50)

    pip = get_pip()
    req_file = BASE_DIR / "requirements.txt"

    if not req_file.exists():
        print(f"  ✗ 找不到 {req_file}")
        return False

    # 先升级 pip
    run_cmd([pip, "install", "--upgrade", "pip"],
            desc="升级 pip")

    # 安装依赖
    result = run_cmd(
        [pip, "install", "-r", str(req_file)],
        desc="安装项目依赖"
    )
    return result


def download_models():
    """下载预训练模型"""
    print("\n" + "=" * 50)
    print("3. 下载 GPT-SoVITS 预训练模型")
    print("=" * 50)
    print("（此步骤可选，也可以后续手动运行 python download_models.py）")

    python = get_python()
    dl_script = BASE_DIR / "download_models.py"
    if dl_script.exists():
        return run_cmd(
            [python, str(dl_script)],
            desc="下载模型"
        )
    return False


def main():
    parser = argparse.ArgumentParser(description="音色克隆服务安装脚本")
    parser.add_argument("--skip-models", action="store_true",
                        help="跳过模型下载")
    args = parser.parse_args()

    print("=" * 50)
    print("音色克隆服务安装")
    print("=" * 50)
    print(f"Python: {sys.executable}")
    print(f"安装目录: {BASE_DIR}")

    steps = [
        ("创建虚拟环境", setup_venv),
        ("安装依赖", install_deps),
    ]

    if not args.skip_models:
        steps.append(("下载模型", download_models))

    all_ok = True
    for desc, fn in steps:
        if not fn():
            print(f"  ⚠ {desc} 步骤出现问题")
            all_ok = False

    print("\n" + "=" * 50)
    if all_ok:
        print("✓ 安装完成！")
        print(f"\n启动服务:")
        print(f"  {get_python()} {BASE_DIR / 'api_server.py'}")
    else:
        print("⚠ 安装完成（部分步骤有警告）")
    print("=" * 50)


if __name__ == "__main__":
    main()
