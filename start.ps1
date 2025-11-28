# URION Trading Bot - Quick Launcher
# Ativa venv automaticamente e inicia o bot

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Urion Trading Bot"

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host "        URION TRADING BOT - QUICK LAUNCHER         " -ForegroundColor Cyan
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-VenvExists {
    if (Test-Path "venv\Scripts\Activate.ps1") {
        return $true
    }
    return $false
}

# INICIO DO SCRIPT
Write-Header

# Verificar se venv existe
if (-not (Test-VenvExists)) {
    Write-Host "[ERRO] Ambiente virtual nao encontrado!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Criando ambiente virtual..." -ForegroundColor Cyan
    
    try {
        python -m venv venv
        Write-Host "[OK] Ambiente virtual criado!" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERRO] Falha ao criar venv: $_" -ForegroundColor Red
        Write-Host ""
        pause
        exit 1
    }
}

Write-Host "[INFO] Ativando ambiente virtual..." -ForegroundColor Cyan

try {
    & ".\venv\Scripts\Activate.ps1"
    Write-Host "[OK] Ambiente virtual ativado!" -ForegroundColor Green
}
catch {
    Write-Host "[ERRO] Falha ao ativar venv: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Execute manualmente:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host ""

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "[ERRO] Python nao encontrado no venv!" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""

# Verificar main.py
if (-not (Test-Path "src\main.py")) {
    Write-Host "[ERRO] Arquivo src\main.py nao encontrado!" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "              INICIANDO BOT...                     " -ForegroundColor Yellow
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dashboard: http://localhost:8050" -ForegroundColor Cyan
Write-Host "Metrics:   http://localhost:8000/metrics" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pressione Ctrl+C para parar o bot" -ForegroundColor Yellow
Write-Host ""

# Iniciar bot
try {
    python src\main.py
}
catch {
    Write-Host ""
    Write-Host "[ERRO] Erro ao executar bot: $_" -ForegroundColor Red
}
finally {
    Write-Host ""
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host "                BOT ENCERRADO                      " -ForegroundColor Yellow
    Write-Host "====================================================" -ForegroundColor Cyan
    Write-Host ""
    pause
}
