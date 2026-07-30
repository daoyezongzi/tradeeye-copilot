@echo off
setlocal

cd /d "%~dp0"

echo [TradeEye Copilot] Installing local dependencies...
python -m pip install -e .[dev]
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [TradeEye Copilot] Opening dashboard: http://127.0.0.1:8000/
start "" "http://127.0.0.1:8000/"

echo.
echo [TradeEye Copilot] Starting real data server...
echo Press Ctrl+C to stop.
python -m uvicorn copilot.api.real_app:app --reload --host 127.0.0.1 --port 8000

endlocal
