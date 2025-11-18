# Script para iniciar bot 24h com monitoramento
# URION Trading Bot

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  URION BOT - MODO 24 HORAS" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Verificar se já existe bot rodando
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "⚠️  Bot já está rodando!" -ForegroundColor Yellow
    Write-Host "Deseja parar e reiniciar? (S/N): " -NoNewline
    $response = Read-Host
    
    if ($response -eq "S" -or $response -eq "s") {
        Write-Host "`n🛑 Parando processos anteriores..." -ForegroundColor Yellow
        Stop-Process -Name python -Force -ErrorAction SilentlyContinue
        Start-Sleep 2
    } else {
        Write-Host "✅ Mantendo bot atual" -ForegroundColor Green
        exit
    }
}

Write-Host "🚀 Iniciando URION Bot em modo 24h...`n" -ForegroundColor Green

# Ativar ambiente virtual
& ".\venv\Scripts\Activate.ps1"

Write-Host "1️⃣  Iniciando Bot Principal (background)..." -ForegroundColor Cyan
# Iniciar bot em nova janela minimizada
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\venv\Scripts\Activate.ps1; python main.py" -WindowStyle Minimized

Start-Sleep 3

Write-Host "2️⃣  Iniciando Monitor 24h (esta janela)...`n" -ForegroundColor Cyan
Start-Sleep 2

# Mostrar instruções
Write-Host "=" -NoNewline -ForegroundColor Green
for ($i = 0; $i -lt 60; $i++) { Write-Host "=" -NoNewline -ForegroundColor Green }
Write-Host ""
Write-Host "  BOT INICIADO COM SUCESSO!" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Green
for ($i = 0; $i -lt 60; $i++) { Write-Host "=" -NoNewline -ForegroundColor Green }
Write-Host "`n"

Write-Host "✅ Bot Principal: " -NoNewline -ForegroundColor Green
Write-Host "Rodando em background (janela minimizada)"

Write-Host "✅ Monitor 24h: " -NoNewline -ForegroundColor Green
Write-Host "Atualizando a cada 30 segundos`n"

Write-Host "CONFIGURACOES ATIVAS:" -ForegroundColor Cyan
Write-Host "   5 Estrategias independentes" -ForegroundColor White
Write-Host "   Ciclos: 60s a 1800s" -ForegroundColor White
Write-Host "   Limite: 2 ordens por estrategia" -ForegroundColor White
Write-Host "   Risk: 2% por trade`n" -ForegroundColor White

Write-Host "Monitor 24h sera exibido abaixo...`n" -ForegroundColor Yellow

Start-Sleep 2

# Iniciar monitor (roda nesta janela)
python monitor_24h.py
