# ============================================
# URION Trading Bot - PowerShell Launcher
# ============================================

$Host.UI.RawUI.WindowTitle = "Urion Trading Bot"

function Show-Header {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "   URION TRADING BOT - LAUNCHER" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Menu {
    Clear-Host
    Show-Header
    Write-Host "1. " -NoNewline -ForegroundColor White
    Write-Host "Verificar Setup" -ForegroundColor Green
    Write-Host "2. " -NoNewline -ForegroundColor White
    Write-Host "Executar Bot" -ForegroundColor Green
    Write-Host "3. " -NoNewline -ForegroundColor White
    Write-Host "Ver Logs (Tempo Real)" -ForegroundColor Green
    Write-Host "4. " -NoNewline -ForegroundColor White
    Write-Host "Editar Configuracoes" -ForegroundColor Green
    Write-Host "5. " -NoNewline -ForegroundColor White
    Write-Host "Editar Credenciais (.env)" -ForegroundColor Green
    Write-Host "6. " -NoNewline -ForegroundColor White
    Write-Host "Sair" -ForegroundColor Red
    Write-Host ""
}

function Test-Python {
    try {
        $pythonVersion = python --version 2>&1
        Write-Host "[OK] " -ForegroundColor Green -NoNewline
        Write-Host "Python encontrado: $pythonVersion"
        return $true
    }
    catch {
        Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
        Write-Host "Python nao encontrado!"
        Write-Host "Por favor, instale Python 3.11+ primeiro."
        return $false
    }
}

function Test-Venv {
    if (Test-Path "venv\Scripts\Activate.ps1") {
        Write-Host "[OK] " -ForegroundColor Green -NoNewline
        Write-Host "Ambiente virtual encontrado"
        return $true
    }
    else {
        Write-Host "[AVISO] " -ForegroundColor Yellow -NoNewline
        Write-Host "Ambiente virtual nao encontrado"
        Write-Host "Criando ambiente virtual..."
        python -m venv venv
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] " -ForegroundColor Green -NoNewline
            Write-Host "Ambiente virtual criado"
            return $true
        }
        else {
            Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
            Write-Host "Falha ao criar ambiente virtual"
            return $false
        }
    }
}

function Enable-Venv {
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Ativando ambiente virtual..."
    & "venv\Scripts\Activate.ps1"
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host "Ambiente virtual ativado"
}

function Test-Dependencies {
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Verificando dependencias..."
    
    python -c "import MetaTrader5" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[AVISO] " -ForegroundColor Yellow -NoNewline
        Write-Host "Dependencias nao instaladas"
        Write-Host "Instalando dependencias..."
        pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] " -ForegroundColor Green -NoNewline
            Write-Host "Dependencias instaladas"
            return $true
        }
        else {
            Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
            Write-Host "Falha ao instalar dependencias"
            return $false
        }
    }
    
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host "Dependencias OK"
    return $true
}

function Test-EnvFile {
    if (Test-Path ".env") {
        Write-Host "[OK] " -ForegroundColor Green -NoNewline
        Write-Host "Arquivo .env encontrado"
        return $true
    }
    else {
        Write-Host "[AVISO] " -ForegroundColor Yellow -NoNewline
        Write-Host "Arquivo .env nao encontrado!"
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Yellow
        Write-Host " CONFIGURE SUAS CREDENCIAIS NO .env" -ForegroundColor Yellow
        Write-Host "============================================" -ForegroundColor Yellow
        Write-Host ""
        
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Host "Arquivo .env.example copiado para .env"
            Write-Host ""
            Write-Host "Configure:" -ForegroundColor Cyan
            Write-Host "  - MT5_LOGIN" -ForegroundColor White
            Write-Host "  - MT5_PASSWORD" -ForegroundColor White
            Write-Host "  - MT5_SERVER" -ForegroundColor White
            Write-Host "  - MT5_PATH" -ForegroundColor White
            Write-Host "  - TELEGRAM_BOT_TOKEN" -ForegroundColor White
            Write-Host "  - TELEGRAM_CHAT_ID" -ForegroundColor White
            Write-Host ""
            
            $open = Read-Host "Abrir .env agora? (S/N)"
            if ($open -eq "S" -or $open -eq "s") {
                notepad .env
            }
            
            Write-Host ""
            Write-Host "Execute este script novamente apos configurar." -ForegroundColor Yellow
            pause
            return $false
        }
        else {
            Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
            Write-Host "Arquivo .env.example nao encontrado"
            return $false
        }
    }
}

function Invoke-VerifySetup {
    Clear-Host
    Show-Header
    Write-Host "VERIFICANDO SETUP" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    
    python verify_setup.py
    
    Write-Host ""
    pause
}

function Invoke-RunBot {
    Clear-Host
    Show-Header
    Write-Host "EXECUTANDO BOT" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Bot iniciando..."
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Pressione Ctrl+C para parar"
    Write-Host ""
    
    try {
        python main.py
    }
    catch {
        Write-Host ""
        Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
        Write-Host "Erro ao executar bot: $_"
    }
    
    Write-Host ""
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Bot encerrado"
    pause
}

function Show-Logs {
    Clear-Host
    Show-Header
    Write-Host "LOGS EM TEMPO REAL" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host "Pressione Ctrl+C para voltar ao menu"
    Write-Host ""
    
    if (Test-Path "logs\urion.log") {
        Get-Content "logs\urion.log" -Wait -Tail 50
    }
    else {
        Write-Host "[AVISO] " -ForegroundColor Yellow -NoNewline
        Write-Host "Arquivo de log nao encontrado"
        Write-Host "Execute o bot primeiro para gerar logs"
        pause
    }
}

function Edit-Config {
    Clear-Host
    Show-Header
    Write-Host "EDITANDO CONFIGURACOES" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    
    if (Test-Path "config\config.yaml") {
        notepad "config\config.yaml"
    }
    else {
        Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
        Write-Host "Arquivo config.yaml nao encontrado"
        pause
    }
}

function Edit-Env {
    Clear-Host
    Show-Header
    Write-Host "EDITANDO CREDENCIAIS" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    
    if (Test-Path ".env") {
        notepad ".env"
    }
    else {
        Write-Host "[ERRO] " -ForegroundColor Red -NoNewline
        Write-Host "Arquivo .env nao encontrado"
        pause
    }
}

# ============================================
# SCRIPT PRINCIPAL
# ============================================

Clear-Host
Show-Header

# Verificações iniciais
if (-not (Test-Python)) {
    pause
    exit 1
}

Write-Host ""

if (-not (Test-Venv)) {
    pause
    exit 1
}

Write-Host ""

# Ativar ambiente virtual
Enable-Venv

Write-Host ""

if (-not (Test-Dependencies)) {
    pause
    exit 1
}

Write-Host ""

if (-not (Test-EnvFile)) {
    exit 0
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " SETUP COMPLETO - PRONTO PARA USAR!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
pause

# Loop do menu
while ($true) {
    Show-Menu
    $choice = Read-Host "Escolha uma opcao (1-6)"
    
    switch ($choice) {
        "1" { Invoke-VerifySetup }
        "2" { Invoke-RunBot }
        "3" { Show-Logs }
        "4" { Edit-Config }
        "5" { Edit-Env }
        "6" {
            Clear-Host
            Show-Header
            Write-Host "ENCERRANDO" -ForegroundColor Cyan
            Write-Host "============================================" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Obrigado por usar o Urion Trading Bot!" -ForegroundColor Green
            Write-Host ""
            Start-Sleep -Seconds 2
            exit 0
        }
        default {
            Write-Host ""
            Write-Host "[ERRO] Opcao invalida!" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
