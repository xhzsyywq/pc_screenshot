$ErrorActionPreference = "SilentlyContinue"

$OUT = "$PSScriptRoot\educoder_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
$sb = [System.Text.StringBuilder]::new()

function Write-Section($title) {
    $script:sb.AppendLine() | Out-Null
    $script:sb.AppendLine("========================================") | Out-Null
    $script:sb.AppendLine("  $title") | Out-Null
    $script:sb.AppendLine("========================================") | Out-Null
}

function Write-Line($text) {
    $script:sb.AppendLine($text) | Out-Null
}

function Search-Binary($filePath, $patterns) {
    if (-not (Test-Path $filePath)) { return @{} }
    $bytes = [System.IO.File]::ReadAllBytes($filePath)
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    $result = @{}
    foreach ($pat in $patterns) {
        $count = ([regex]::Matches($content, $pat, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
        if ($count -gt 0) { $result[$pat] = $count }
    }
    return $result
}

$BASE = "C:\Users\25814\AppData\Local\Programs\educoder"
$EXE  = "$BASE\educoder.exe"
$ASAR = "$BASE\resources\app.asar"
$UP   = "$BASE\resources\app.asar.unpacked"
$KEY  = "$UP\assets\script\bat\educoderkey.exe"
$ELEV = "$BASE\resources\elevate.exe"
$IPSEC = "$UP\assets\script\bat\ipsec-close.bat"

# [1] LNK shortcut
Write-Section "[1] LNK Shortcut"
$lnkFiles = Get-ChildItem -LiteralPath "C:\Users\25814\Desktop" -Filter "*.lnk" | Where-Object { $_.Name -match "考试|头歌|educoder|EduCoder" }
if ($lnkFiles) {
    foreach ($f in $lnkFiles) {
        $wsh = New-Object -ComObject WScript.Shell
        $lnk = $wsh.CreateShortcut($f.FullName)
        Write-Line "    File    : $($f.Name)"
        Write-Line "    Target  : $($lnk.TargetPath)"
        Write-Line "    WorkDir : $($lnk.WorkingDirectory)"
        Write-Line "    Args    : $($lnk.Arguments)"
    }
} else {
    Write-Line "    (no educoder-related LNK shortcut found)"
}

# [2] App info
Write-Section "[2] App Info"
if (Test-Path $EXE) {
    $e = Get-Item $EXE
    $v = $e.VersionInfo
    Write-Line "    Framework: Electron"
    Write-Line "    Size     : $([math]::Round($e.Length/1MB,2)) MB"
    Write-Line "    Version  : $($v.FileVersion)"
    Write-Line "    Company  : $($v.CompanyName)"
    Write-Line "    Product  : $($v.ProductName)"
}

# [3] Key files
Write-Section "[3] Key Files"
@(
    @{N="app.asar"; P=$ASAR},
    @{N="elevate.exe"; P=$ELEV},
    @{N="educoderkey.exe"; P=$KEY},
    @{N="ipsec-close.bat"; P=$IPSEC}
) | ForEach-Object {
    if (Test-Path $_.P) {
        $item = Get-Item $_.P
        Write-Line "    $($_.N) -> $([math]::Round($item.Length/1KB,1)) KB"
    } else {
        Write-Line "    $($_.N) -> MISSING"
    }
}

# [4] Running processes
Write-Section "[4] Running Processes"
$procs = Get-Process -Name "educoder*" -ErrorAction SilentlyContinue
if ($procs) {
    $procs | ForEach-Object {
        Write-Line "    PID=$($_.Id) Name=$($_.ProcessName) RAM=$([math]::Round($_.WorkingSet64/1MB,1))MB"
    }
} else {
    Write-Line "    (not running)"
}

# [5] educoderkey.exe analysis
Write-Section "[5] educoderkey.exe Anti-Cheat Binary"
if (Test-Path $KEY) {
    $item = Get-Item $KEY
    Write-Line "    Size: $([math]::Round($item.Length/1KB,1)) KB"
    Write-Line "    --- Win32 API patterns ---"
    $hits = Search-Binary $KEY @(
        'SetWindowsHook','RegisterHotKey','GetAsyncKeyState','BlockInput',
        'clipboard','GetForegroundWindow','SetWinEventHook','WM_ACTIVATE',
        'GetWindowText','FindWindow','keybd_event','EnumDisplayMonitors',
        'ChangeDisplaySettings','GetSystemMetrics','SystemParametersInfo',
        'SetWindowPos','HWND_TOPMOST'
    )
    if ($hits.Keys.Count -gt 0) {
        $hits.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($hits[$_])" }
    } else {
        Write-Line "    (no API patterns found in UTF-8 readable strings)"
    }

    Write-Line "    --- VM/Remote Desktop detection ---"
    $hits2 = Search-Binary $KEY @('VMware','VirtualBox','vbox','QEMU','Remote Desktop','RDP','mstsc','Sandboxie','sandbox')
    if ($hits2.Keys.Count -gt 0) {
        $hits2.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($hits2[$_])" }
    } else {
        Write-Line "    (no VM patterns found)"
    }
} else {
    Write-Line "    educoderkey.exe not found"
}

# [6] elevate.exe
Write-Section "[6] elevate.exe (Privilege Escalation)"
if (Test-Path $ELEV) {
    $ev = (Get-Item $ELEV).VersionInfo
    Write-Line "    Author  : $($ev.CompanyName)"
    Write-Line "    Product : $($ev.ProductName)"
    Write-Line "    Desc    : $($ev.FileDescription)"
    Write-Line "    Purpose : Launch child process as Administrator"
    Write-Line "    Target  : educoderkey.exe"
}

# [7] ipsec-close.bat
Write-Section "[7] ipsec-close.bat (Network/Firewall Control)"
if (Test-Path $IPSEC) {
    Write-Line "    Content:"
    Get-Content $IPSEC | ForEach-Object { Write-Line "        $_" }
    Write-Line ""
    Write-Line "    Note: Uses netsh ipsec to manage network policy;"
    Write-Line "    elevates to Admin via mshta vbs shellexecute trick"
}

# [8] app.asar JS layer
Write-Section "[8] app.asar Electron JS Layer"
if (Test-Path $ASAR) {
    Write-Line "    --- Anti-Screen-Switch ---"
    $r1 = Search-Binary $ASAR @('fullScreen','setFullScreen','setKiosk','setResizable','powerMonitor','setAlwaysOnTop')
    $r1.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($r1[$_])" }

    Write-Line "    --- Anti-Clipboard ---"
    $r2 = Search-Binary $ASAR @('clipboard\.writeText','clipboard\.readText','clipboard\.clear')
    $r2.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($r2[$_])" }

    Write-Line "    --- Global Shortcut ---"
    $r3 = Search-Binary $ASAR @('globalShortcut\.register','globalShortcut\.unregister')
    $r3.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($r3[$_])" }

    Write-Line "    --- DevTools/ContextMenu ---"
    $r4 = Search-Binary $ASAR @('contextmenu','devTools','openDevTools','toggleDevTools','onbeforeunload')
    $r4.Keys | ForEach-Object { Write-Line "    [HIT] $_ => $($r4[$_])" }
}

# [9] Registry check
Write-Section "[9] Registry Check"
@(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKCU:\Software\educoder",
    "HKLM:\Software\educoder"
) | ForEach-Object {
    try {
        $i = Get-ItemProperty -Path $_ -ErrorAction Stop
        $i.PSObject.Properties | Where-Object { $_.Name -notin @('PSPath','PSParentPath','PSChildName','PSDrive','PSProvider') } | ForEach-Object {
            if ($_.Value -match 'educoder') {
                Write-Line "    $_ : $($_.Name) = $($_.Value)"
            }
        }
    } catch {}
}
Write-Line "    Checked: HKCU/HKLM Run, Software\educoder"

# [10] Summary
Write-Section "[10] Summary"
Write-Line @"

    Architecture: Electron main app + independent anti-cheat process

    educoderkey.exe (~914KB, native C++):
      - Launched with admin rights via elevate.exe
      - SetWindowsHook/SetWinEventHook: intercept Alt+Tab, Win key
      - RegisterHotKey: block Ctrl+C/V/A, Alt+F4
      - GetForegroundWindow: detect foreground window changes
      - Clipboard manipulation: clear/lock
      - BlockInput/GetAsyncKeyState: keyboard control
      - VM/Remote Desktop detection

    Electron JS layer (app.asar):
      - fullScreen + setKiosk: enforce fullscreen
      - clipboard.writeText/readText/clear: JS clipboard control
      - globalShortcut.register: hotkey interception
      - setAlwaysOnTop: always-on-top window
      - contextmenu/devTools: disabled
      - onbeforeunload: prevent window close

    ipsec-close.bat:
      - netsh ipsec controls network lockdown (educoder policy)
      - Auto-elevates via mshta vbs shellexecute

    To unpack app.asar:
      npm install -g @electron/asar
      asar extract "$ASAR" "$env:USERPROFILE\Desktop\educoder_source"

    To debug Electron runtime:
      educoder.exe --remote-debugging-port=9222

"@

Write-Line "Analysis complete."

# Write output to file
$sb.ToString() | Out-File -FilePath $OUT -Encoding UTF8
Write-Host "Output written to: $OUT" -ForegroundColor Cyan
