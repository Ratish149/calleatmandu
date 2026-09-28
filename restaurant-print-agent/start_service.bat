@echo off
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b 1
)

echo Killing any existing RestaurantPrintAgent processes...
taskkill /F /IM RestaurantPrintAgent.exe >nul 2>&1
net stop RestaurantPrintAgent >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting RestaurantPrintAgent service (1 instance only)...
net start RestaurantPrintAgent
if errorlevel 1 (
    echo [ERROR] Could not start service. Run install_service.bat first if not installed.
    pause
    exit /b 1
)

echo.
echo [DONE] Service started - running in background.
echo Auto-starts on every computer restart.
tasklist | findstr RestaurantPrintAgent
pause
