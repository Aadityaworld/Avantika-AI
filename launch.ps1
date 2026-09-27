<#
.SYNOPSIS
    Production bootstrapper for Local AI Assistant.
    Ensures Ollama daemon is running and llama3.2 is pulled before launching the app.
.USAGE
    .\launch.ps1
#>

$ErrorActionPreference = "Stop"
$OllamaUrl   = "http://127.0.0.1:11434"
$TagsUrl     = "$OllamaUrl/api/tags"
$TargetModel = "llama3.2"
$ExePath     = "$PSScriptRoot\dist\LocalAIAssistant\LocalAIAssistant.exe"
$FallbackCmd = "python"
$FallbackArg = "$PSScriptRoot\main.py"

function Write-Banner {
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  Local AI Assistant — Production Launcher"   -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
}

function Test-OllamaRunning {
    try {
        $resp = Invoke-RestMethod -Uri $TagsUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
        return $resp
    } catch {
        return $null
    }
}

function Start-OllamaDaemon {
    Write-Host "[INFO] Starting Ollama daemon in background..." -ForegroundColor Yellow
    $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue)?.Source
    if (-not $ollamaExe) {
        Write-Host "[WARN] 'ollama' not found in PATH. Install from https://ollama.ai and retry." -ForegroundColor Red
        return $false
    }
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden -PassThru | Out-Null
    # Allow daemon to start
    Start-Sleep -Seconds 3
    return $true
}

function Ensure-ModelPresent($tags) {
    $models = $tags.models | ForEach-Object { $_.name -replace ":latest", "" }
    if ($TargetModel -in $models) {
        Write-Host "[OK] Model '$TargetModel' is available locally." -ForegroundColor Green
        return
    }
    Write-Host "[INFO] Model '$TargetModel' not found. Pulling now (this may take a few minutes)..." -ForegroundColor Yellow
    $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue)?.Source
    if (-not $ollamaExe) {
        Write-Host "[WARN] Cannot pull model — 'ollama' not in PATH." -ForegroundColor Red
        return
    }
    & $ollamaExe pull $TargetModel
    Write-Host "[OK] Model pull complete." -ForegroundColor Green
}

# ── Main ──────────────────────────────────────────────────────────────────────
Write-Banner

# 1. Check / start Ollama daemon
$tags = Test-OllamaRunning
if ($null -eq $tags) {
    $started = Start-OllamaDaemon
    if ($started) {
        $tags = Test-OllamaRunning
        if ($null -eq $tags) {
            Write-Host "[WARN] Ollama daemon failed to respond. App will run in deterministic fallback mode." -ForegroundColor Yellow
        } else {
            Write-Host "[OK] Ollama daemon started successfully." -ForegroundColor Green
        }
    }
} else {
    Write-Host "[OK] Ollama daemon already running at $OllamaUrl" -ForegroundColor Green
}

# 2. Ensure llama3.2 is pulled
if ($null -ne $tags) {
    Ensure-ModelPresent $tags
}

# 3. Launch the application
Write-Host ""
if (Test-Path $ExePath) {
    Write-Host "[LAUNCH] Starting compiled application: $ExePath" -ForegroundColor Cyan
    Start-Process -FilePath $ExePath
} else {
    Write-Host "[LAUNCH] Compiled binary not found. Falling back to: python main.py" -ForegroundColor Yellow
    & $FallbackCmd $FallbackArg
}
