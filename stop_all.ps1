# Script para parar todos os componentes do Urion Bot
# Execute com: powershell -ExecutionPolicy Bypass -File stop_all.ps1

Write-Host "=" * 60
Write-Host "  URION TRADING BOT - PARANDO" -ForegroundColor Yellow
Write-Host "=" * 60
Write-Host ""

# Matar processos Python relacionados ao Urion
Write-Host "Parando processos Python..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object {
    $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    if ($cmdLine -match "urion|server\.py|main\.py") {
        Write-Host "  Parando PID $($_.Id): $cmdLine" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force
    }
}

# Matar processos Node relacionados ao Urion
Write-Host "Parando processos Node..." -ForegroundColor Yellow
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host ""
Write-Host "=" * 60
Write-Host "  URION BOT PARADO" -ForegroundColor Green
Write-Host "=" * 60
