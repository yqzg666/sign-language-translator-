@echo off
chcp 65001 > nul
echo ========================================
echo   手语翻译系统 - 启动中...
echo ========================================
cd /d "%~dp0"

echo [1/2] 启动 Django 后端 (端口 8000)...
start "Django后端" cmd /c ".venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak > nul

echo [2/2] 启动 Web 前端 (端口 5173)...
start "Vue前端" cmd /c "cd sign_language ^&^& npm run dev"

echo ========================================
echo   启动完成！
echo   后端: http://127.0.0.1:8000
echo   前端: http://localhost:5173
echo ========================================
pause
