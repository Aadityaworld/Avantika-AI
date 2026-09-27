<#
.SYNOPSIS
    Single-command launcher for the Autonomous Desktop Voice Assistant.
.DESCRIPTION
    Verifies Python installation, checks local Ollama service status,
    and starts the assistant application.
#>

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Starting Autonomous Voice Assistant Launcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Verify Python availability
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and add it to your system PATH." -ForegroundColor Yellow
    exit 1
}

# 2. Check local Ollama status on http://127.0.0.1:11434
$ollamaUrl = "http://127.0.0.1:11434/api/tags"
try {
    $response = Invoke-RestMethod -Uri $ollamaUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[OK] Local Ollama service active on http://127.0.0.1:11434" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Ollama service is not reachable on http://127.0.0.1:11434." -ForegroundColor Yellow
    Write-Host "       The assistant will start in Deterministic Fallback Mode." -ForegroundColor Yellow
    Write-Host "       To enable full LLM reasoning, run 'ollama serve' in a separate terminal." -ForegroundColor DarkYellow
}

# 3. Launch the assistant
Write-Host "`nLaunching assistant (main.py)..." -ForegroundColor Cyan
python main.py
