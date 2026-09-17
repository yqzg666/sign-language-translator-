#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

# 确保推理引擎目录可被导入（inference.py 位于 main/src/），
# 避免仅在 sign_api.views 顶层注入 sys.path 时，某些启动/加载顺序下报 "No module named 'inference'"
BASE_DIR = Path(__file__).resolve().parent.parent  # main/
_SRC = BASE_DIR / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
