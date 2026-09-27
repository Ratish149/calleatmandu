@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo       Restaurant Thermal Print Agent - Windows Build Script      
echo ================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.12+ (64-bit) from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Checking Python environment...
python -c "import sys; print(f'Detected Python {sys.version}')"

:: 2. Install dependencies
echo [2/4] Installing / Updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 3. Clean previous build directories
echo [3/4] Cleaning previous build folders...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

:: 4. Build single executable with PyInstaller
echo [4/4] Compiling RestaurantPrintAgent.exe with PyInstaller...
pyinstaller --clean ^
    --onefile ^
    --noconsole ^
    --name RestaurantPrintAgent ^
    --icon=assets/icon.ico ^
    --hidden-import=websockets ^
    --hidden-import=websockets.legacy ^
    --hidden-import=websockets.legacy.client ^
    --hidden-import=win32print ^
    --hidden-import=win32service ^
    --hidden-import=win32serviceutil ^
    --hidden-import=win32event ^
    --hidden-import=servicemanager ^
    --hidden-import=sqlite3 ^
    agent.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo [ERROR] PyInstaller build failed! Review output above.
    echo ================================================================
    pause
    exit /b 1
)

echo.
echo ================================================================
echo [SUCCESS] Build finished!
echo Executable: dist\RestaurantPrintAgent.exe
echo.
echo Next steps:
echo 1. Copy 'dist\RestaurantPrintAgent.exe' to 'C:\RestaurantPrintAgent\'
echo 2. Copy 'config.json.example' as 'C:\RestaurantPrintAgent\config.json'
echo 3. Run 'install_service.bat' as Administrator
echo ================================================================
echo.
pause
