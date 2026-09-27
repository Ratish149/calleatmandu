@echo off
setlocal

echo ================================================================
echo       Restaurant Thermal Print Agent - Windows Build Script      
echo ================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 goto CHECK_PY_LAUNCHER

set PYTHON_BIN=python
goto START_BUILD

:CHECK_PY_LAUNCHER
py --version >nul 2>&1
if errorlevel 1 goto NO_PYTHON
set PYTHON_BIN=py -3
goto START_BUILD

:START_BUILD
echo [1/3] Using Python:
%PYTHON_BIN% --version
echo.
echo Installing requirements and PyInstaller...
%PYTHON_BIN% -m pip install --upgrade pip
%PYTHON_BIN% -m pip install -r requirements.txt
%PYTHON_BIN% -m pip install pyinstaller

echo.
echo [2/3] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo.
echo [3/3] Compiling RestaurantPrintAgent.exe...
%PYTHON_BIN% -m PyInstaller --clean --onefile --noconsole --name RestaurantPrintAgent agent.py

if errorlevel 1 goto BUILD_FAILED

echo.
echo ================================================================
echo [SUCCESS] Build finished successfully!
echo Executable is located at:
echo   dist\RestaurantPrintAgent.exe
echo.
echo Next step:
echo Copy RestaurantPrintAgent.exe and config.json to C:\RestaurantPrintAgent\
echo ================================================================
pause
exit /b 0

:NO_PYTHON
echo ================================================================
echo [ERROR] Python is not installed or not added to PATH!
echo.
echo Solution:
echo 1. Download Python from: https://www.python.org/downloads/
echo 2. Run the installer.
echo 3. CRITICAL: Check the box at the bottom:
echo    [X] Add python.exe to PATH
echo 4. Complete installation, reopen Command Prompt, and run build.bat.
echo ================================================================
pause
exit /b 1

:BUILD_FAILED
echo ================================================================
echo [ERROR] PyInstaller build failed! Review the error output above.
echo ================================================================
pause
exit /b 1
