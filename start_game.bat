@echo off
setlocal

echo ===================================================
echo       LuluGo Server Launcher for Windows
echo ===================================================

REM Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Please install Python.
    pause
    exit /b 1
)

REM Start Backend Server
echo [INFO] Starting Backend Server (main.py)...
echo Logs will be written to server.log
start "LuluGo Backend" cmd /c "python main.py & pause"

REM Check for Ngrok
where ngrok >nul 2>nul
if %errorlevel% neq 0 (
    if exist ngrok.exe (
        echo [INFO] Ngrok found in current directory.
        set "NGROK_CMD=ngrok.exe"
    ) else (
        echo [WARNING] Ngrok not found in PATH or current directory.
        echo Please download ngrok from https://ngrok.com/download
        echo and place ngrok.exe in this folder.
        echo.
        echo Skipping Ngrok startup. LAN access is still possible.
        pause
        goto :SkipNgrok
    )
) else (
    set "NGROK_CMD=ngrok"
)

REM Start Ngrok
echo [INFO] Starting Ngrok on port 8000...
start "Ngrok Tunnel" cmd /k "%NGROK_CMD% http 8000"

:SkipNgrok
echo.
echo [INFO] Startup initiated. 
echo 1. Backend window should open.
echo 2. Ngrok window should open (if available).
echo.
echo [INFO] Waiting for server to initialize...
timeout /t 3 >nul
echo [INFO] Opening web browser...
start http://localhost:8000/static/index.html

echo.
echo Press any key to close this launcher...
pause