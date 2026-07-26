@echo off
chcp 65001 >nul
echo === Research Agent Startup ===
echo.
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
echo Stopping old processes...
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul
set BACKEND_PORT=8010
echo.
echo [1/3] Starting backend API (http://localhost:%BACKEND_PORT%)...
start "ResearchAgent-Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"
echo Waiting for backend...
set BACKEND_OK=0
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set BACKEND_OK=1
        goto :backend_ready
    )
)
:backend_ready
echo.
echo [2/3] Starting frontend dev server (Vite + Vue 3)...
echo.
echo   NOTE: First-time setup requires running these commands once:
echo     cd frontend
echo     cmd /c npm install
echo.
start "ResearchAgent-Frontend" cmd /c "cd /d %PROJECT_DIR%frontend && npx vite --host"
echo Waiting for frontend...
set FRONTEND_OK=0
for /l %%i in (1,1,20) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set FRONTEND_OK=1
        goto :frontend_ready
    )
)
:frontend_ready
echo.
echo [3/3] Service Status:
echo ========================================
if "%BACKEND_OK%"=="1" ( echo   Backend API:  http://localhost:%BACKEND_PORT% [OK] ) else ( echo   Backend API:  not started [ERROR] )
if "%FRONTEND_OK%"=="1" ( echo   Frontend UI:  http://localhost:5173 [OK] ) else ( echo   Frontend UI:  not started [ERROR] )
echo   API Docs:     http://localhost:%BACKEND_PORT%/docs
echo ========================================
echo.
if "%BACKEND_OK%"=="1" if "%FRONTEND_OK%"=="1" (
    echo All services running. Opening browser...
    start http://localhost:5173
    pause >nul
) else (
    echo Some services failed to start. Check output above.
    pause >nul
)
