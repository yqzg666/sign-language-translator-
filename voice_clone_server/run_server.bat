@echo off
chcp 65001 >nul
title 音色克隆服务

echo ============================================
echo   音色克隆 API 服务器
echo ============================================

cd /d "%~dp0"

:: 使用项目 Python 环境（复用 main 的虚拟环境或系统 Python）
set PYTHON=C:\Users\syt\AppData\Local\Programs\Python\Python312\python.exe

:: 检查模型
echo 正在检查模型文件...
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from api_server import check_models; m=check_models(); print(f'缺失 {len(m)} 个模型'); [print(f'  - {x}') for x in m]"
if %ERRORLEVEL% neq 0 (
    echo ⚠ 模型检查失败
)

:: 启动服务
echo.
echo 启动音色克隆服务 (端口 9880)...
%PYTHON% api_server.py --port 9880

pause
