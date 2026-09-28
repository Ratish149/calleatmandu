@echo off
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b 1
)
echo Starting RestaurantPrintAgent service...
net start RestaurantPrintAgent
if errorlevel 1 (
    echo [ERROR] Could not start service. Run install_service.bat first if not installed.
    pause
    exit /b 1
)
echo [DONE] Service started and running in background.
echo Auto-starts on every computer restart.
pause
