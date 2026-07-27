@echo off
chcp 65001 >nul
title 音色克隆服务

echo ============================================
echo   音色克隆服务 - 一键启动
echo ============================================

cd /d "%~dp0"

:: 使用项目虚拟环境的 Python
set PYTHON=..\main\.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [错误] 未找到虚拟环境: %PYTHON%
    echo 请先在 main 目录下创建虚拟环境
    pause
    exit /b 1
)

:: 启动 GPT-SoVITS 引擎 (端口 9870)
echo [1/2] 启动 GPT-SoVITS 音色克隆引擎 (9870端口)...
if exist "GPT-SoVITS\api_v2.py" (
    start "GPT-SoVITS" cmd /c "%PYTHON% GPT-SoVITS\api_v2.py -a 127.0.0.1 -p 9870 -c GPT_SoVITS/configs/tts_infer.yaml"
    echo   推理引擎已启动（首次启动会自动下载 BERT/HuBERT 模型）
) else (
    echo   GPT-SoVITS 未安装，将使用 edge-tts fallback 模式
)

timeout /t 5 /nobreak >nul

:: 启动代理服务 (端口 9880)
echo [2/2] 启动音色克隆代理服务 (9880端口)...
start "Voice Clone Proxy" cmd /c "%PYTHON% api_server.py --port 9880"

echo.
echo ============================================
echo   启动完成！
echo   GPT-SoVITS: http://localhost:9870（推理引擎）
echo   克隆代理:   http://localhost:9880（API 接口）
echo ============================================
echo.
pause
