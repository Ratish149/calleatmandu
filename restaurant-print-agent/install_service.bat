@echo off
setlocal

echo ================================================================
echo    CallEatMandu Restaurant Print Agent - Service Installation    
echo ================================================================
echo.

:: 1. Verify Administrative Privileges
net session >nul 2>&1
if errorlevel 1 goto NOT_ADMIN

set APP_DIR=%~dp0
set APP_DIR=%APP_DIR:~0,-1%
set EXE_PATH=%APP_DIR%\RestaurantPrintAgent.exe
set CONFIG_PATH=%APP_DIR%\config.json

echo Target Directory: %APP_DIR%
echo Executable Path:  %EXE_PATH%
echo Config Path:      %CONFIG_PATH%
echo.

:: 2. Check if config.json exists
if exist "%CONFIG_PATH%" goto CHECK_EXE

if exist "%APP_DIR%\config.json.example" (
    echo [INFO] Creating initial config.json from template...
    copy "%APP_DIR%\config.json.example" "%CONFIG_PATH%" >nul
    echo Please make sure %CONFIG_PATH% has the correct branch_id and printer_name!
) else (
    echo [WARNING] %CONFIG_PATH% was not found. Please create it.
)

:CHECK_EXE
if exist "%EXE_PATH%" goto INSTALL_EXE
goto CHECK_PYTHON

:INSTALL_EXE
echo [1/3] Registering Windows Service using RestaurantPrintAgent.exe...
sc stop RestaurantPrintAgent >nul 2>&1
sc delete RestaurantPrintAgent >nul 2>&1
timeout /t 2 /nobreak >nul

sc create RestaurantPrintAgent binPath= "\"%EXE_PATH%\"" start= auto DisplayName= "Restaurant Thermal Print Agent"
sc description RestaurantPrintAgent "CallEatMandu background thermal printing agent for KOT and Customer Bills."
sc failure RestaurantPrintAgent reset= 86400 actions= restart/5000/restart/10000/restart/30000

echo [2/3] Service registered successfully.
echo [3/3] Starting RestaurantPrintAgent service...
net start RestaurantPrintAgent
goto DONE

:CHECK_PYTHON
python --version >nul 2>&1
if errorlevel 1 goto NO_EXECUTABLE_OR_PYTHON

echo [INFO] Executable not found. Installing service via Python...
python "%APP_DIR%\service.py" --startup auto install
python "%APP_DIR%\service.py" start
goto DONE

:NOT_ADMIN
echo ================================================================
echo [ERROR] This script MUST be executed as Administrator!
echo Right-click 'install_service.bat' and select 'Run as administrator'.
echo ================================================================
pause
exit /b 1

:NO_EXECUTABLE_OR_PYTHON
echo ================================================================
echo [ERROR] Neither RestaurantPrintAgent.exe nor Python was found!
echo Please compile the EXE using build.bat or copy RestaurantPrintAgent.exe here.
echo ================================================================
pause
exit /b 1

:DONE
echo.
echo ================================================================
echo [SUCCESS] Restaurant Print Agent Service installed and running!
echo.
echo Check status:
echo   sc query RestaurantPrintAgent
echo.
echo View live logs:
echo   type "%APP_DIR%\logs\agent.log"
echo ================================================================
pause
exit /b 0
