# Start Dashboard
# Inicia o dashboard web do Urion Trading Bot

Write-Host "`n" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Yellow
Write-Host "  URION DASHBOARD - INICIANDO  " -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Yellow
Write-Host "`n" -ForegroundColor Cyan

# Ativa venv
.\venv\Scripts\Activate.ps1

Write-Host " Iniciando servidor Flask..." -ForegroundColor Cyan
Write-Host "`n Dashboard disponível em:" -ForegroundColor Green
Write-Host "   http://localhost:5000`n" -ForegroundColor Cyan

# Inicia dashboard
python src\dashboard\app.py
