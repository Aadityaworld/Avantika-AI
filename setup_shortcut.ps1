<#
.SYNOPSIS
    Registers the Local AI Assistant shortcut in the Windows Start Menu.
.DESCRIPTION
    Creates 'Avantika.lnk' in the Windows Programs folder with custom icon,
    working directory, and compiled exe target (or pythonw fallback).
#>

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
if (-not $projectRoot) {
    $projectRoot = (Get-Location).Path
}

$programsFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)
$shortcutPath   = Join-Path -Path $programsFolder -ChildPath "Avantika.lnk"
$iconPath       = Join-Path -Path $projectRoot -ChildPath "app.ico"
$compiledExe    = Join-Path -Path $projectRoot -ChildPath "dist\Avantika\Avantika.exe"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Windows Start Menu Shortcut Registration"     -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "[INFO] Project Root : $projectRoot"
Write-Host "[INFO] Programs Dir : $programsFolder"

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)

if (Test-Path $compiledExe) {
    Write-Host "[INFO] Targeting compiled binary: $compiledExe" -ForegroundColor Green
    $shortcut.TargetPath = $compiledExe
    $shortcut.Arguments  = ""
} else {
    $pythonwCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($pythonwCmd) {
        $pythonw = $pythonwCmd.Source
    } else {
        $pythonw = "pythonw.exe"
    }
    Write-Host "[INFO] Compiled binary not found. Targeting pythonw with main.py fallback: $pythonw" -ForegroundColor Yellow
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments  = "`"$projectRoot\main.py`""
}

$shortcut.WorkingDirectory = $projectRoot

if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath, 0"
    Write-Host "[INFO] Bound Icon Location: $iconPath, 0" -ForegroundColor Green
} else {
    Write-Host "[WARN] app.ico not found at $iconPath" -ForegroundColor Yellow
}

$shortcut.Description = "Local AI Voice & Text Assistant (Zero-Credit Offline LLM)"
$shortcut.Save()

Write-Host "`n[OK] Registered shortcut successfully:" -ForegroundColor Green
Write-Host "     $shortcutPath" -ForegroundColor Cyan

