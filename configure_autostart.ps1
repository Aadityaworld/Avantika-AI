param(
    [ValidateSet("enable", "disable", "status")]
    [string]$Action = "status"
)

$AppTitle = "AvantikaAIAssistant"
$RegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$ProjectDir = $PSScriptRoot
$ExePath = Join-Path $ProjectDir "dist\Avantika\Avantika.exe"

if (-Not (Test-Path $ExePath)) {
    # Fallback to python execution for dev environment
    $ExePath = "pythonw.exe `"$ProjectDir\main.py`""
} else {
    $ExePath = "`"$ExePath`""
}

$Command = "$ExePath --minimized"

try {
    if ($Action -eq "enable") {
        Set-ItemProperty -Path $RegPath -Name $AppTitle -Value $Command -ErrorAction Stop
        Write-Host "[OK] Autostart ENABLED for $AppTitle." -ForegroundColor Green
    } elseif ($Action -eq "disable") {
        Remove-ItemProperty -Path $RegPath -Name $AppTitle -ErrorAction Ignore
        Write-Host "[OK] Autostart DISABLED for $AppTitle." -ForegroundColor Yellow
    } else {
        $key = Get-ItemProperty -Path $RegPath -Name $AppTitle -ErrorAction Ignore
        if ($null -ne $key) {
            Write-Host "[STATUS] Autostart is ENABLED." -ForegroundColor Green
            Write-Host "         Command: $($key.$AppTitle)"
        } else {
            Write-Host "[STATUS] Autostart is DISABLED." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "[FAIL] Registry access failed: $_" -ForegroundColor Red
    exit 1
}
exit 0

