@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: YouTube Content Assistant - Windows Installation Script
:: ============================================================

set "INSTALL_PATH=%USERPROFILE%\youtube-content-assistant"
set "REPO_URL=https://github.com/mil2cle/youtube.git"

echo.
echo ============================================================
echo   YouTube Content Assistant - Windows Installer
echo   Version 1.4
echo ============================================================
echo.

:: Check Python
echo [1/7] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!] Python not found
    echo   [i] Please install Python 3.11+ from https://www.python.org/downloads/
    echo   [i] Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   [OK] Found Python %PYTHON_VER%

:: Check Git
echo [2/7] Checking Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!] Git not found
    echo   [i] Please install Git from https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)
for /f "tokens=3" %%i in ('git --version 2^>^&1') do set GIT_VER=%%i
echo   [OK] Found Git %GIT_VER%

:: Clone repository
echo [3/7] Cloning project from GitHub...
if exist "%INSTALL_PATH%" (
    echo   [!] Folder %INSTALL_PATH% already exists
    set /p CONFIRM="  Delete and reinstall? (y/n): "
    if /i "!CONFIRM!"=="y" (
        rmdir /s /q "%INSTALL_PATH%"
    ) else (
        echo   [i] Skipping clone, using existing folder
        goto :skip_clone
    )
)
git clone %REPO_URL% "%INSTALL_PATH%"
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to clone project
    pause
    exit /b 1
)
echo   [OK] Clone successful
:skip_clone

:: Change to project directory
cd /d "%INSTALL_PATH%"

:: Create Virtual Environment
echo [4/7] Creating Virtual Environment...
if exist "venv" (
    echo   [i] Virtual Environment already exists
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   [ERROR] Failed to create Virtual Environment
        pause
        exit /b 1
    )
)
echo   [OK] Virtual Environment ready

:: Install Dependencies
echo [5/7] Installing Dependencies (this may take a while)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
set PYTHONUTF8=1
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo   [OK] Dependencies installed

:: Create Database
echo [6/7] Creating Database...
set /p SEED_DATA="  Create sample data? (y/n): "
if /i "%SEED_DATA%"=="y" (
    python scripts/init_db.py --seed --yes
) else (
    python scripts/init_db.py --yes
)
if %errorlevel% neq 0 (
    echo   [WARNING] Database creation may have issues
) else (
    echo   [OK] Database created
)

:: Create Shortcut Scripts
echo [7/7] Creating Shortcut Scripts...

:: Create run_dashboard.bat
(
echo @echo off
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Dashboard
echo echo   Starting Dashboard...
echo echo   URL: http://localhost:8501
echo echo ============================================================
echo echo.
echo start http://localhost:8501
echo streamlit run dashboard/app.py
echo pause
) > "%INSTALL_PATH%\run_dashboard.bat"

:: Create fetch_research.bat
(
echo @echo off
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Fetch Research Data
echo echo ============================================================
echo echo.
echo python scripts/fetch_research.py --all
echo echo.
echo echo Done!
echo pause
) > "%INSTALL_PATH%\fetch_research.bat"

:: Create train_playbook.bat
(
echo @echo off
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Train Playbook
echo echo ============================================================
echo echo.
echo python scripts/train_playbook.py --demo
echo echo.
echo echo Done!
echo pause
) > "%INSTALL_PATH%\train_playbook.bat"

echo   [OK] Shortcut Scripts created

:: Show summary
echo.
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo   Install location: %INSTALL_PATH%
echo.
echo   Files created:
echo   - run_dashboard.bat   : Open Dashboard
echo   - fetch_research.bat  : Fetch Anime Research data
echo   - train_playbook.bat  : Train Playbook Model
echo.
echo   How to use:
echo   1. Go to folder %INSTALL_PATH%
echo   2. Double-click 'run_dashboard.bat'
echo   3. Open browser to http://localhost:8501
echo.
echo ============================================================
echo.

set /p OPEN_DASHBOARD="Open Dashboard now? (y/n): "
if /i "%OPEN_DASHBOARD%"=="y" (
    start "" "%INSTALL_PATH%\run_dashboard.bat"
)

echo.
echo Press Enter to close this window...
pause >nul
