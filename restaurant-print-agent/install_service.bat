@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo    CallEatMandu Restaurant Print Agent - Service Installation    
echo ================================================================
echo.

:: 1. Verify Administrative Privileges
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] This script MUST be executed as Administrator!
    echo Right-click 'install_service.bat' and select 'Run as administrator'.
    pause
    exit /b 1
)

set APP_DIR=%~dp0
set APP_DIR=%APP_DIR:~0,-1%
set EXE_PATH=%APP_DIR%\RestaurantPrintAgent.exe
set CONFIG_PATH=%APP_DIR%\config.json

echo Target Directory: %APP_DIR%
echo Executable Path:  %EXE_PATH%
echo Config Path:      %CONFIG_PATH%
echo.

:: 2. Check if config.json exists
if not exist "%CONFIG_PATH%" (
    echo [WARNING] config.json was not found in %APP_DIR%!
    if exist "%APP_DIR%\config.json.example" (
        echo Creating initial config.json from template...
        copy "%APP_DIR%\config.json.example" "%CONFIG_PATH%"
        echo Please edit %CONFIG_PATH% with your restaurant branch_id, printer_name, and token!
    ) else (
        echo Please create %CONFIG_PATH% before starting the service.
    )
    echo.
)

:: 3. Check for Executable or Python
if exist "%EXE_PATH%" (
    echo [1/3] Registering Windows Service using RestaurantPrintAgent.exe...
    
    :: Remove existing service if present
    sc stop RestaurantPrintAgent >nul 2>&1
    sc delete RestaurantPrintAgent >nul 2>&1
    timeout /t 2 /nobreak >nul

    :: Create native Windows Service with Auto-Start
    sc create RestaurantPrintAgent binPath= "\"%EXE_PATH%\"" start= auto DisplayName= "Restaurant Thermal Print Agent"
    
    :: Set description
    sc description RestaurantPrintAgent "CallEatMandu background thermal printing agent for KOT and Customer Bills."
    
    :: Configure auto-recovery (restart after 5s, 10s, 30s upon crash)
    sc failure RestaurantPrintAgent reset= 86400 actions= restart/5000/restart/10000/restart/30000

    echo [2/3] Service registered successfully.
    echo [3/3] Starting RestaurantPrintAgent service...
    net start RestaurantPrintAgent

) else (
    echo [INFO] Executable not found. Checking for Python development environment...
    python --version >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Installing service via Python win32service...
        python "%APP_DIR%\service.py" --startup auto install
        python "%APP_DIR%\service.py" start
    ) else (
        echo [ERROR] Neither RestaurantPrintAgent.exe nor Python was found in %APP_DIR%!
        echo Please compile the EXE using build.bat or copy RestaurantPrintAgent.exe here.
        pause
        exit /b 1
    )
)

echo.
echo ================================================================
echo [SUCCESS] Restaurant Print Agent Service installed and started!
echo.
echo To check status:
echo   sc query RestaurantPrintAgent
echo.
echo To view live logs:
echo   type "%APP_DIR%\logs\agent.log"
echo ================================================================
echo.
pause
