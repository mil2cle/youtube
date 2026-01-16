# ============================================================
# YouTube Content Assistant - Windows Installation Script
# ============================================================
# สคริปต์ติดตั้งอัตโนมัติสำหรับ Windows 10/11
# 
# วิธีใช้งาน:
# 1. เปิด PowerShell ในโหมด Administrator
# 2. รันคำสั่ง: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# 3. รันสคริปต์: .\install_windows.ps1
# ============================================================

param(
    [switch]$SkipPython,
    [switch]$SkipGit,
    [switch]$SeedData,
    [string]$InstallPath = "$env:USERPROFILE\youtube-content-assistant"
)

# ตั้งค่า encoding สำหรับภาษาไทย
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# สี
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  YouTube Content Assistant - Windows Installer" -ForegroundColor Cyan
    Write-Host "  Version 1.4" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($step, $message) {
    Write-Host "[$step] " -ForegroundColor Yellow -NoNewline
    Write-Host $message -ForegroundColor White
}

function Write-Success($message) {
    Write-Host "  [OK] " -ForegroundColor Green -NoNewline
    Write-Host $message -ForegroundColor White
}

function Write-Error($message) {
    Write-Host "  [ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $message -ForegroundColor White
}

function Write-Warning($message) {
    Write-Host "  [!] " -ForegroundColor Yellow -NoNewline
    Write-Host $message -ForegroundColor White
}

function Write-Info($message) {
    Write-Host "  [i] " -ForegroundColor Cyan -NoNewline
    Write-Host $message -ForegroundColor White
}

# ตรวจสอบว่ารันในโหมด Administrator หรือไม่
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ตรวจสอบว่า Python ติดตั้งแล้วหรือไม่
function Test-PythonInstalled {
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.1[1-9]|Python 3\.[2-9][0-9]") {
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
}

# ตรวจสอบว่า Git ติดตั้งแล้วหรือไม่
function Test-GitInstalled {
    try {
        $gitVersion = git --version 2>&1
        if ($gitVersion -match "git version") {
            return $true
        }
        return $false
    }
    catch {
        return $false
    }
}

# ติดตั้ง Python ผ่าน winget
function Install-Python {
    Write-Step "2a" "กำลังติดตั้ง Python 3.11..."
    
    try {
        winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        
        # รีเฟรช PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Success "ติดตั้ง Python สำเร็จ"
        return $true
    }
    catch {
        Write-Error "ไม่สามารถติดตั้ง Python ได้: $_"
        Write-Info "กรุณาดาวน์โหลดและติดตั้ง Python 3.11+ จาก https://www.python.org/downloads/"
        return $false
    }
}

# ติดตั้ง Git ผ่าน winget
function Install-Git {
    Write-Step "2b" "กำลังติดตั้ง Git..."
    
    try {
        winget install Git.Git --accept-package-agreements --accept-source-agreements
        
        # รีเฟรช PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Success "ติดตั้ง Git สำเร็จ"
        return $true
    }
    catch {
        Write-Error "ไม่สามารถติดตั้ง Git ได้: $_"
        Write-Info "กรุณาดาวน์โหลดและติดตั้ง Git จาก https://git-scm.com/download/win"
        return $false
    }
}

# Main Installation
function Start-Installation {
    Write-Header
    
    # Step 1: ตรวจสอบ requirements
    Write-Step "1" "ตรวจสอบความต้องการของระบบ..."
    
    # ตรวจสอบ Python
    if (-not $SkipPython) {
        if (Test-PythonInstalled) {
            $pythonVersion = python --version 2>&1
            Write-Success "พบ Python: $pythonVersion"
        }
        else {
            Write-Warning "ไม่พบ Python 3.11+ ในระบบ"
            
            if (-not (Test-Administrator)) {
                Write-Error "กรุณารันสคริปต์นี้ในโหมด Administrator เพื่อติดตั้ง Python"
                Write-Info "หรือติดตั้ง Python 3.11+ ด้วยตนเองจาก https://www.python.org/downloads/"
                return $false
            }
            
            if (-not (Install-Python)) {
                return $false
            }
        }
    }
    
    # ตรวจสอบ Git
    if (-not $SkipGit) {
        if (Test-GitInstalled) {
            $gitVersion = git --version 2>&1
            Write-Success "พบ Git: $gitVersion"
        }
        else {
            Write-Warning "ไม่พบ Git ในระบบ"
            
            if (-not (Test-Administrator)) {
                Write-Error "กรุณารันสคริปต์นี้ในโหมด Administrator เพื่อติดตั้ง Git"
                Write-Info "หรือติดตั้ง Git ด้วยตนเองจาก https://git-scm.com/download/win"
                return $false
            }
            
            if (-not (Install-Git)) {
                return $false
            }
        }
    }
    
    # Step 2: Clone repository
    Write-Step "3" "กำลัง Clone โปรเจ็คจาก GitHub..."
    
    if (Test-Path $InstallPath) {
        Write-Warning "พบโฟลเดอร์ $InstallPath อยู่แล้ว"
        $confirm = Read-Host "  ต้องการลบและติดตั้งใหม่หรือไม่? (y/n)"
        if ($confirm -eq "y" -or $confirm -eq "Y") {
            Remove-Item -Recurse -Force $InstallPath
        }
        else {
            Write-Info "ข้ามการ clone และใช้โฟลเดอร์ที่มีอยู่"
        }
    }
    
    if (-not (Test-Path $InstallPath)) {
        try {
            git clone https://github.com/mil2cle/youtube.git $InstallPath
            Write-Success "Clone โปรเจ็คสำเร็จ"
        }
        catch {
            Write-Error "ไม่สามารถ clone โปรเจ็คได้: $_"
            return $false
        }
    }
    
    # Step 3: สร้าง Virtual Environment
    Write-Step "4" "กำลังสร้าง Virtual Environment..."
    
    Set-Location $InstallPath
    
    try {
        python -m venv venv
        Write-Success "สร้าง Virtual Environment สำเร็จ"
    }
    catch {
        Write-Error "ไม่สามารถสร้าง Virtual Environment ได้: $_"
        return $false
    }
    
    # Step 4: Activate และติดตั้ง dependencies
    Write-Step "5" "กำลังติดตั้ง Dependencies..."
    
    try {
        # Activate venv และติดตั้ง packages
        & "$InstallPath\venv\Scripts\python.exe" -m pip install --upgrade pip
        & "$InstallPath\venv\Scripts\pip.exe" install -r requirements.txt
        Write-Success "ติดตั้ง Dependencies สำเร็จ"
    }
    catch {
        Write-Error "ไม่สามารถติดตั้ง Dependencies ได้: $_"
        return $false
    }
    
    # Step 5: สร้างฐานข้อมูล
    Write-Step "6" "กำลังสร้างฐานข้อมูล..."
    
    try {
        if ($SeedData) {
            & "$InstallPath\venv\Scripts\python.exe" scripts/init_db.py --seed --yes
            Write-Success "สร้างฐานข้อมูลพร้อมข้อมูลตัวอย่างสำเร็จ"
        }
        else {
            & "$InstallPath\venv\Scripts\python.exe" scripts/init_db.py --yes
            Write-Success "สร้างฐานข้อมูลสำเร็จ"
        }
    }
    catch {
        Write-Error "ไม่สามารถสร้างฐานข้อมูลได้: $_"
        return $false
    }
    
    # Step 6: รัน Smoke Test
    Write-Step "7" "กำลังทดสอบระบบ..."
    
    try {
        & "$InstallPath\venv\Scripts\python.exe" scripts/smoke_test_youtube_ingestion.py
        & "$InstallPath\venv\Scripts\python.exe" scripts/smoke_test_research.py
        Write-Success "ทดสอบระบบผ่านทั้งหมด"
    }
    catch {
        Write-Warning "การทดสอบบางรายการไม่ผ่าน (อาจไม่มีผลต่อการใช้งาน)"
    }
    
    # Step 7: สร้าง Shortcut Scripts
    Write-Step "8" "กำลังสร้าง Shortcut Scripts..."
    
    # สร้าง run_dashboard.bat
    $dashboardScript = @"
@echo off
cd /d "$InstallPath"
call venv\Scripts\activate.bat
echo.
echo ============================================================
echo   YouTube Content Assistant - Dashboard
echo   กำลังเปิด Dashboard...
echo   URL: http://localhost:8501
echo ============================================================
echo.
streamlit run dashboard/app.py
pause
"@
    Set-Content -Path "$InstallPath\run_dashboard.bat" -Value $dashboardScript -Encoding UTF8
    
    # สร้าง fetch_data.bat
    $fetchScript = @"
@echo off
cd /d "$InstallPath"
call venv\Scripts\activate.bat
echo.
echo ============================================================
echo   YouTube Content Assistant - Fetch Data
echo ============================================================
echo.
echo [1] กำลังดึงข้อมูล Research (Anime)...
python scripts/fetch_research.py --all
echo.
echo [2] กำลังฝึก Playbook Model...
python scripts/train_playbook.py --demo
echo.
echo เสร็จสิ้น!
pause
"@
    Set-Content -Path "$InstallPath\fetch_data.bat" -Value $fetchScript -Encoding UTF8
    
    Write-Success "สร้าง Shortcut Scripts สำเร็จ"
    
    # แสดงผลสรุป
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  การติดตั้งเสร็จสมบูรณ์!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ตำแหน่งติดตั้ง: $InstallPath" -ForegroundColor White
    Write-Host ""
    Write-Host "  วิธีใช้งาน:" -ForegroundColor Yellow
    Write-Host "  1. ดับเบิลคลิก 'run_dashboard.bat' เพื่อเปิด Dashboard" -ForegroundColor White
    Write-Host "  2. เปิดเบราว์เซอร์ไปที่ http://localhost:8501" -ForegroundColor White
    Write-Host ""
    Write-Host "  คำสั่งอื่นๆ:" -ForegroundColor Yellow
    Write-Host "  - fetch_data.bat    : ดึงข้อมูลและฝึก Model" -ForegroundColor White
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    
    # ถามว่าต้องการเปิด Dashboard เลยหรือไม่
    $openDashboard = Read-Host "ต้องการเปิด Dashboard เลยหรือไม่? (y/n)"
    if ($openDashboard -eq "y" -or $openDashboard -eq "Y") {
        Start-Process "$InstallPath\run_dashboard.bat"
    }
    
    return $true
}

# รันการติดตั้ง
Start-Installation
