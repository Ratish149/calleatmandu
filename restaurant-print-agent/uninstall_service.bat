@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   CallEatMandu Restaurant Print Agent - Service Uninstallation   
echo ================================================================
echo.

:: 1. Verify Administrative Privileges
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] This script MUST be executed as Administrator!
    echo Right-click 'uninstall_service.bat' and select 'Run as administrator'.
    pause
    exit /b 1
)

set APP_DIR=%~dp0
set APP_DIR=%APP_DIR:~0,-1%

echo [1/3] Stopping RestaurantPrintAgent service...
net stop RestaurantPrintAgent >nul 2>&1
sc stop RestaurantPrintAgent >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/3] Deleting Windows service registration...
sc delete RestaurantPrintAgent >nul 2>&1

:: Also try python service remover if present
if exist "%APP_DIR%\service.py" (
    python "%APP_DIR%\service.py" stop >nul 2>&1
    python "%APP_DIR%\service.py" remove >nul 2>&1
)

echo [3/3] Cleanup complete.
echo.
echo ================================================================
echo [SUCCESS] RestaurantPrintAgent service has been completely uninstalled.
echo Note: Your config.json and logs have been kept intact in:
echo %APP_DIR%
echo ================================================================
echo.
pause
