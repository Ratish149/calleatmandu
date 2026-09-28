@echo off
setlocal

echo ================================================================
echo    CallEatMandu Restaurant Print Agent - Update Script
echo ================================================================
echo.

:: 1. Require Administrator
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Run this script as Administrator!
    echo Right-click update.bat and select "Run as administrator".
    pause
    exit /b 1
)

set INSTALL_DIR=C:\RestaurantPrintAgent
set SERVICE_NAME=RestaurantPrintAgent
set NEW_EXE=%~dp0RestaurantPrintAgent.exe

:: 2. Check new exe exists beside this script
if not exist "%NEW_EXE%" (
    echo [ERROR] RestaurantPrintAgent.exe not found next to this script.
    echo Place the new RestaurantPrintAgent.exe in the same folder as update.bat.
    pause
    exit /b 1
)

:: 3. Stop the service
echo [1/4] Stopping %SERVICE_NAME% service...
net stop %SERVICE_NAME% >nul 2>&1
timeout /t 2 /nobreak >nul

:: 4. Force kill if still running
tasklist | findstr /I "%SERVICE_NAME%.exe" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Process still running, force killing...
    taskkill /F /IM "%SERVICE_NAME%.exe" >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo [2/4] Service stopped.

:: 5. Replace the exe
echo [3/4] Installing new RestaurantPrintAgent.exe...
copy /Y "%NEW_EXE%" "%INSTALL_DIR%\RestaurantPrintAgent.exe"
if errorlevel 1 (
    echo [ERROR] Failed to copy new exe. Check permissions on %INSTALL_DIR%.
    pause
    exit /b 1
)

echo [4/4] Starting %SERVICE_NAME% service...
net start %SERVICE_NAME%
if errorlevel 1 (
    echo [ERROR] Failed to start service. Check logs at %INSTALL_DIR%\logs\agent.log
    pause
    exit /b 1
)

echo.
echo ================================================================
echo [SUCCESS] Agent updated and running!
echo.
echo To check status : sc query %SERVICE_NAME%
echo To view logs    : type "%INSTALL_DIR%\logs\agent.log"
echo ================================================================
pause
exit /b 0
