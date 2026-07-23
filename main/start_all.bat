@echo off
chcp 65001 >nul
title 手语翻译系统 - 启动脚本

echo ============================================
echo    手语 AI 系统 - 一键启动
echo ============================================
echo.

:: 获取脚本所在目录
set "ROOT=%~dp0"
cd /d "%ROOT%"

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行：
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: 检查前端依赖
if not exist "sign_language\node_modules" (
    echo [信息] 安装前端依赖...
    cd sign_language
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
    cd ..
)

:: 启动 Django 后端（新窗口）
echo [1/3] 启动 Django 后端（8000端口）...
start "Django Backend" cmd /c ".venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000"

:: 等待后端启动
echo [等待] 后端初始化中...
timeout /t 5 /nobreak >nul

:: 启动 Vue 前端（新窗口）
echo [2/3] 启动 Vue 前端（5173端口）...
start "Vue Frontend" cmd /c "cd sign_language && npx vite --host 0.0.0.0 --port 5173"

:: 启动音色克隆服务（新窗口，可选）
echo [3/3] 启动音色克隆服务（9880端口）...
if exist "..\voice_clone_server\api_server.py" (
    start "Voice Clone" cmd /c "C:\Users\syt\AppData\Local\Programs\Python\Python312\python.exe ..\voice_clone_server\api_server.py --port 9880"
    echo   音色克隆服务已启动（无模型时自动回退 edge-tts）
) else (
    echo   音色克隆服务未安装，配音将使用默认 edge-tts
)

echo.
echo ============================================
echo    启动完成！
echo.
echo    前端:  http://localhost:5173
echo    后端:  http://localhost:8000
echo    音色克隆: http://localhost:9880 (如已安装)
echo ============================================
echo.
echo 首次使用请清除 localStorage 缓存：
echo   F12 → 控制台 → localStorage.clear(); location.href='/'
echo. 
pause
