@echo off
chcp 65001 >nul
echo === Research Agent 一键启动 ===
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo 正在清理残留进程...
:: Kill all python.exe processes related to this project
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Verify ports are free
netstat -ano | findstr ":8080 " >nul 2>&1
if not errorlevel 1 (
    echo   端口 8080 仍被占用，尝试强制释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do (
        taskkill /f /pid %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

netstat -ano | findstr ":8000 " >nul 2>&1
if not errorlevel 1 (
    echo   端口 8000 仍被占用，尝试强制释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        taskkill /f /pid %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

echo.
echo 启动后端 API 服务 (http://localhost:8000)...
start "ResearchAgent-Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 5 /nobreak >nul

echo 启动前端界面 (http://localhost:8080)...
start "ResearchAgent-Frontend" cmd /c ".venv\Scripts\python.exe -m frontend.app"

echo.
echo === 服务已启动 ===
echo   后端 API:  http://localhost:8000
echo   前端界面:  http://localhost:8080
echo.
echo 按任意键打开前端界面...
pause >nul
start http://localhost:8080
