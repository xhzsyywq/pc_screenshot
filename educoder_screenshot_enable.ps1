$ErrorActionPreference = "Stop"

# ============================================================
#  Self-elevate to Administrator
# ============================================================
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[*] Requesting Administrator privileges..." -ForegroundColor Yellow
    $args = "-ExecutionPolicy Bypass -NoProfile -File `"$($MyInvocation.MyCommand.Path)`""
    Start-Process PowerShell -Verb RunAs -ArgumentList $args
    exit 0
}

# ============================================================
#  Load pre-compiled StealthCapture.dll
# ============================================================
$DLL = "$PSScriptRoot\StealthCapture.dll"
if (-not (Test-Path $DLL)) {
    Write-Host "ERROR: $DLL not found. Compile first:" -ForegroundColor Red
    Write-Host "  csc /t:library /out:StealthCapture.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll StealthCapture.cs" -ForegroundColor Yellow
    exit 1
}
Add-Type -Path $DLL

# ============================================================
#  Main
# ============================================================
$OUT_FILE = "$PSScriptRoot\screenshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Stealth Screenshot"                   -ForegroundColor Cyan
Write-Host "    DXGI GPU-level  (primary)"           -ForegroundColor Green
Write-Host "    GDI  BitBlt     (fallback)"          -ForegroundColor Green
Write-Host "    No BlockInput   (not called)"        -ForegroundColor Green
Write-Host "    No clipboard    (file only)"         -ForegroundColor Green
Write-Host "    No window API   (zero hooks)"        -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Try DXGI first, fall back to GDI
try {
    Write-Host "[1] DXGI Desktop Duplication..." -ForegroundColor Yellow
    [StealthCapture.Capture]::DxgiToFile($OUT_FILE)
    Write-Host "    DXGI OK — GPU-level capture" -ForegroundColor Green
} catch {
    Write-Host "    DXGI failed: $_" -ForegroundColor Red
    Write-Host "[2] GDI BitBlt fallback..." -ForegroundColor Yellow
    try {
        [StealthCapture.Capture]::GdiToFile($OUT_FILE)
        Write-Host "    GDI OK — screen DC read" -ForegroundColor Green
    } catch {
        Write-Host "    GDI also failed: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Saved: $OUT_FILE" -ForegroundColor Green
Write-Host "Zero window / hook / BlockInput / clipboard calls made." -ForegroundColor DarkGray

Start-Sleep -Seconds 2
