@echo off
chcp 65001 > nul
echo ========================================
echo   手语翻译系统 - 启动中...
echo ========================================
cd /d "%~dp0"

:: 检测虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境: .venv\
    echo 请先执行: python -m venv .venv
    echo 然后: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/4] 启动 Django 后端 (端口 8000)...
start "Django后端" cmd /c ".venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000"
timeout /t 3 /nobreak > nul

echo [2/4] 启动 Web 前端 (端口 5173)...
if exist "sign_language\node_modules" (
    start "Vue前端" cmd /c "cd sign_language && npm run dev"
) else (
    echo   [警告] sign_language\node_modules 不存在，请先执行 cd sign_language ^&^& npm install
)

echo [3/4] 启动 GPT-SoVITS 音色克隆引擎 (端口 9870)...
if exist "voice_clone_server\GPT-SoVITS\api_v2.py" (
    start "GPT-SoVITS" cmd /c "cd /d voice_clone_server\GPT-SoVITS && ..\..\.venv\Scripts\python.exe api_v2.py -a 127.0.0.1 -p 9870 -c GPT_SoVITS/configs/tts_infer.yaml"
    echo   真实音色克隆引擎已启动（首次启动会自动下载模型，可能需要数分钟）
) else (
    echo   GPT-SoVITS 未安装，将使用 edge-tts fallback 模式
)

timeout /t 2 /nobreak > nul

echo [4/4] 启动音色克隆代理服务 (端口 9880)...
if exist "voice_clone_server\api_server.py" (
    start "音色克隆" cmd /c ".venv\Scripts\python.exe voice_clone_server\api_server.py --port 9880"
)

echo ========================================
echo   启动完成！
echo   后端:      http://127.0.0.1:8000
echo   前端:      http://localhost:5173
echo   音色克隆:  http://localhost:9880
echo   GPT-SoVITS: http://localhost:9870
echo ========================================
echo.
echo 如果前端页面没有自动打开，请在浏览器访问 http://localhost:5173
echo.
pause
