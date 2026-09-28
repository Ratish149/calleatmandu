@echo off
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Run as Administrator!
    pause
    exit /b 1
)
echo Stopping RestaurantPrintAgent service...
net stop RestaurantPrintAgent
taskkill /F /IM RestaurantPrintAgent.exe >nul 2>&1
echo [DONE] Service stopped.
pause
