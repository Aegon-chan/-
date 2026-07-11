@echo off
chcp 65001 >nul
echo === Research Agent 一键启�?===
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo 正在清理残留进程...
echo [1/4] 强制终止�?Python 进程...

:: 方案 A: 按进程名杀死所�?python.exe
taskkill /f /im python.exe 2>&1
if errorlevel 1 (
    echo   [警告] 未发现运行中�?python.exe 进程
) else (
    echo   [OK] 已终止旧 python.exe 进程
)

:: 等待端口释放
timeout /t 2 /nobreak >nul

:: 方案 B: 确认端口已释放，未释放则�?PID 杀
set PORT_8080_FREE=1
netstat -ano | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT_8080_FREE=0
    echo   [警告] 端口 8080 仍被占用，尝试按 PID 杀�?..
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak >nul
    netstat -ano | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo   [错误] 端口 8080 无法释放，请手动检�?
    ) else (
        echo   [OK] 端口 8080 已释�?
        set PORT_8080_FREE=1
    )
)

set PORT_8010_FREE=1
netstat -ano | findstr ":8010 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT_8010_FREE=0
    echo   [警告] 端口 8010 仍被占用，尝试按 PID 杀�?..
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8010 " ^| findstr "LISTENING"') do (
        taskkill /f /pid %%a
    )
    timeout /t 2 /nobreak >nul
    netstat -ano | findstr ":8010 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo   [错误] 端口 8010 无法释放，请手动检�?
    ) else (
        echo   [OK] 端口 8010 已释�??
        set PORT_8010_FREE=1
    )
)

set BACKEND_PORT=8010
echo.
echo [2/4] 启动后端 API 服务 (http://localhost:8010)...
start "ResearchAgent-Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

:: 等待后端启动
echo   等待后端服务就绪...
set BACKEND_OK=0
for /l %%i in (1,1,10) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":8010 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set BACKEND_OK=1
        goto :backend_ready
    )
)
:backend_ready
if "%BACKEND_OK%"=="1" (
    echo   [OK] 后端 API 已启�?(http://localhost:8010)
) else (
    echo   [警告] 后端服务未能确认启动，请检查端�?
)

echo.
echo [3/4] 启动前端界面 (http://localhost:8080)...
start "ResearchAgent-Frontend" cmd /c ".venv\Scripts\python.exe -m frontend.app"

echo   等待前端服务就绪...
set FRONTEND_OK=0
for /l %%i in (1,1,20) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set FRONTEND_OK=1
        goto :frontend_ready
    )
)
:frontend_ready
if "%FRONTEND_OK%"=="1" (
    echo   [OK] 前端已启�?(http://localhost:8080)
) else (
    echo   [警告] 前端服务未能确认启动，请检查端�?
)

echo.
echo [4/4] 服务状态检�?..
echo ========================================
if "%BACKEND_OK%"=="1" ( echo   后端 API:  http://localhost:8010 [OK] ) else ( echo   后端 API:  未启�?[错误] )
if "%FRONTEND_OK%"=="1" ( echo   前端界面:  http://localhost:8080 [OK] ) else ( echo   前端界面:  未启�?[错误] )
echo ========================================
echo.

:: 只有两个服务都启动成功才自动打开浏览�?
if "%BACKEND_OK%"=="1" if "%FRONTEND_OK%"=="1" (
    echo 启动完成，正在打开浏览�?..
    start http://localhost:8080
    pause >nul
) else (
    echo 部分服务启动失败，请根据上方提示检查后重试
    pause >nul
)
