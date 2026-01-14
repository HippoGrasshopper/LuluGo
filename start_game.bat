@echo off
setlocal

echo ===================================================
echo       LuluGo Server Launcher for VS Code
echo ===================================================

REM Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Please install Python.
    pause
    exit /b 1
)

REM (Backend will be started in foreground at the end)

:SkipNgrok
echo.
echo.
echo [INFO] Startup initiated.

REM Schedule Browser Open (Background)
REM echo [INFO] Browser will open in 3 seconds...
REM start /B cmd /c "timeout /t 3 >nul & start http://localhost:8000/"

REM Start Backend Server (Foreground)
echo [INFO] Starting Backend Server (main.py)...
echo [INFO] Press Ctrl+C to stop the server.
echo.
python main.py

echo.
echo Server stopped.
pause