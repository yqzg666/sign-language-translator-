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
echo [1/2] 启动 Django 后端（8000端口）...
start "Django Backend" cmd /c ".venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000"

:: 等待后端启动
echo [等待] 后端初始化中...
timeout /t 5 /nobreak >nul

:: 启动 Vue 前端（新窗口）
echo [2/2] 启动 Vue 前端（5173端口）...
start "Vue Frontend" cmd /c "cd sign_language && npx vite --host 0.0.0.0 --port 5173"

echo.
echo ============================================
echo    启动完成！
echo.
echo    前端: http://localhost:5173
echo    后端: http://localhost:8000
echo ============================================
echo.
echo 首次使用请清除 localStorage 缓存：
echo   F12 → 控制台 → localStorage.clear(); location.href='/'
echo. 
pause
