# Start Dashboard Web - Urion Trading Bot

Write-Host "`n" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  🌐 URION TRADING BOT - DASHBOARD WEB" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "`n"

Write-Host " 📊 Iniciando dashboard..." -ForegroundColor White
Write-Host "`n"

# Ativar venv se existir
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "   Ativando ambiente virtual..." -ForegroundColor Gray
    & .\venv\Scripts\Activate.ps1
}

Write-Host "   Acessível em: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:5000" -ForegroundColor Cyan
Write-Host "`n"
Write-Host " ⚡ Auto-atualização a cada 5 segundos" -ForegroundColor Green
Write-Host " 🔄 Pressione CTRL+C para parar" -ForegroundColor Yellow
Write-Host "`n"

# Iniciar dashboard
python dashboard_web.py
