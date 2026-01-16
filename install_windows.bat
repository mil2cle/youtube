@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
:: YouTube Content Assistant - Windows Installation Script
:: ============================================================
:: สคริปต์ติดตั้งอัตโนมัติสำหรับ Windows 10/11
:: 
:: วิธีใช้งาน:
:: 1. ดับเบิลคลิกไฟล์นี้
:: 2. หรือเปิด Command Prompt แล้วรัน: install_windows.bat
:: ============================================================

set "INSTALL_PATH=%USERPROFILE%\youtube-content-assistant"
set "REPO_URL=https://github.com/mil2cle/youtube.git"

echo.
echo ============================================================
echo   YouTube Content Assistant - Windows Installer
echo   Version 1.4
echo ============================================================
echo.

:: ตรวจสอบ Python
echo [1/7] ตรวจสอบ Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!] ไม่พบ Python ในระบบ
    echo   [i] กรุณาติดตั้ง Python 3.11+ จาก https://www.python.org/downloads/
    echo   [i] ตอนติดตั้งให้เลือก "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo   [OK] พบ Python %PYTHON_VER%

:: ตรวจสอบ Git
echo [2/7] ตรวจสอบ Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!] ไม่พบ Git ในระบบ
    echo   [i] กรุณาติดตั้ง Git จาก https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)
for /f "tokens=3" %%i in ('git --version 2^>^&1') do set GIT_VER=%%i
echo   [OK] พบ Git %GIT_VER%

:: Clone repository
echo [3/7] Clone โปรเจ็คจาก GitHub...
if exist "%INSTALL_PATH%" (
    echo   [!] พบโฟลเดอร์ %INSTALL_PATH% อยู่แล้ว
    set /p CONFIRM="  ต้องการลบและติดตั้งใหม่หรือไม่? (y/n): "
    if /i "!CONFIRM!"=="y" (
        rmdir /s /q "%INSTALL_PATH%"
    ) else (
        echo   [i] ข้ามการ clone และใช้โฟลเดอร์ที่มีอยู่
        goto :skip_clone
    )
)
git clone %REPO_URL% "%INSTALL_PATH%"
if %errorlevel% neq 0 (
    echo   [ERROR] ไม่สามารถ clone โปรเจ็คได้
    pause
    exit /b 1
)
echo   [OK] Clone โปรเจ็คสำเร็จ
:skip_clone

:: เปลี่ยนไปยังโฟลเดอร์โปรเจ็ค
cd /d "%INSTALL_PATH%"

:: สร้าง Virtual Environment
echo [4/7] สร้าง Virtual Environment...
if exist "venv" (
    echo   [i] พบ Virtual Environment อยู่แล้ว
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   [ERROR] ไม่สามารถสร้าง Virtual Environment ได้
        pause
        exit /b 1
    )
)
echo   [OK] Virtual Environment พร้อมใช้งาน

:: ติดตั้ง Dependencies
echo [5/7] ติดตั้ง Dependencies (อาจใช้เวลาสักครู่)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
set PYTHONUTF8=1
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo   [ERROR] ไม่สามารถติดตั้ง Dependencies ได้
    pause
    exit /b 1
)
echo   [OK] ติดตั้ง Dependencies สำเร็จ

:: สร้างฐานข้อมูล
echo [6/7] สร้างฐานข้อมูล...
set /p SEED_DATA="  ต้องการสร้างข้อมูลตัวอย่างด้วยหรือไม่? (y/n): "
if /i "%SEED_DATA%"=="y" (
    python scripts/init_db.py --seed --yes
) else (
    python scripts/init_db.py --yes
)
if %errorlevel% neq 0 (
    echo   [WARNING] อาจมีปัญหาในการสร้างฐานข้อมูล
) else (
    echo   [OK] สร้างฐานข้อมูลสำเร็จ
)

:: สร้าง Shortcut Scripts
echo [7/7] สร้าง Shortcut Scripts...

:: สร้าง run_dashboard.bat
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Dashboard
echo echo   กำลังเปิด Dashboard...
echo echo   URL: http://localhost:8501
echo echo ============================================================
echo echo.
echo start http://localhost:8501
echo streamlit run dashboard/app.py
echo pause
) > "%INSTALL_PATH%\run_dashboard.bat"

:: สร้าง fetch_research.bat
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Fetch Research Data
echo echo ============================================================
echo echo.
echo python scripts/fetch_research.py --all
echo echo.
echo echo เสร็จสิ้น!
echo pause
) > "%INSTALL_PATH%\fetch_research.bat"

:: สร้าง train_playbook.bat
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%INSTALL_PATH%"
echo call venv\Scripts\activate.bat
echo echo.
echo echo ============================================================
echo echo   YouTube Content Assistant - Train Playbook
echo echo ============================================================
echo echo.
echo python scripts/train_playbook.py --demo
echo echo.
echo echo เสร็จสิ้น!
echo pause
) > "%INSTALL_PATH%\train_playbook.bat"

echo   [OK] สร้าง Shortcut Scripts สำเร็จ

:: แสดงผลสรุป
echo.
echo ============================================================
echo   การติดตั้งเสร็จสมบูรณ์!
echo ============================================================
echo.
echo   ตำแหน่งติดตั้ง: %INSTALL_PATH%
echo.
echo   ไฟล์ที่สร้าง:
echo   - run_dashboard.bat   : เปิด Dashboard
echo   - fetch_research.bat  : ดึงข้อมูล Anime Research
echo   - train_playbook.bat  : ฝึก Playbook Model
echo.
echo   วิธีใช้งาน:
echo   1. ไปที่โฟลเดอร์ %INSTALL_PATH%
echo   2. ดับเบิลคลิก 'run_dashboard.bat'
echo   3. เปิดเบราว์เซอร์ไปที่ http://localhost:8501
echo.
echo ============================================================
echo.

set /p OPEN_DASHBOARD="ต้องการเปิด Dashboard เลยหรือไม่? (y/n): "
if /i "%OPEN_DASHBOARD%"=="y" (
    start "" "%INSTALL_PATH%\run_dashboard.bat"
)

echo.
echo กด Enter เพื่อปิดหน้าต่างนี้...
pause >nul
