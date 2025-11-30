# Urion Bot Control Script
# Script para gerenciar o bot de forma profissional

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'force-start', 'supervisor')]
    [string]$Action = 'status'
)

$BotDir = "c:\Users\Administrator\Desktop\urion"
$PythonExe = "$BotDir\venv\Scripts\python.exe"
$MainScript = "$BotDir\src\main.py"
$SupervisorScript = "$BotDir\supervisor.py"
$PidFile = "$BotDir\urion_bot.pid"

function Get-BotStatus {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "BOT RODANDO" -ForegroundColor Green
            Write-Host "   PID: $pid"
            Write-Host "   CPU: $($process.CPU)s"
            Write-Host "   RAM: $([math]::Round($process.WorkingSet64/1MB, 2)) MB"
            Write-Host "   Threads: $($process.Threads.Count)"
            Write-Host "   Inicio: $($process.StartTime)"
            return $true
        } else {
            Write-Host "PID file existe mas processo nao encontrado" -ForegroundColor Red
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            return $false
        }
    } else {
        Write-Host "BOT NAO ESTA RODANDO" -ForegroundColor Red
        return $false
    }
}

function Start-Bot {
    param([bool]$Force = $false)
    
    if ((Get-BotStatus) -and -not $Force) {
        Write-Host "Bot ja esta rodando. Use 'force-start' para reiniciar." -ForegroundColor Yellow
        return
    }
    
    Write-Host "Iniciando bot..." -ForegroundColor Cyan
    
    if ($Force) {
        & $PythonExe $MainScript --force
    } else {
        & $PythonExe $MainScript
    }
}

function Stop-Bot {
    if (!(Test-Path $PidFile)) {
        Write-Host "PID file nao encontrado" -ForegroundColor Yellow
        return
    }
    
    $pid = Get-Content $PidFile
    Write-Host "Parando bot (PID: $pid)..." -ForegroundColor Yellow
    
    try {
        Stop-Process -Id $pid -Force
        Start-Sleep -Seconds 2
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Bot parado" -ForegroundColor Green
    } catch {
        Write-Host "Erro ao parar bot: $_" -ForegroundColor Red
    }
}

function Restart-Bot {
    Write-Host "Reiniciando bot..." -ForegroundColor Cyan
    Stop-Bot
    Start-Sleep -Seconds 3
    Start-Bot
}

function Start-Supervisor {
    Write-Host "Iniciando bot com supervisor (restart automatico)..." -ForegroundColor Cyan
    Write-Host "   Pressione Ctrl+C para parar" -ForegroundColor Gray
    & $PythonExe $SupervisorScript
}

# Executar ação
switch ($Action) {
    'start' {
        Start-Bot
    }
    'stop' {
        Stop-Bot
    }
    'restart' {
        Restart-Bot
    }
    'status' {
        Get-BotStatus
        Write-Host "`nProcessos Python:" -ForegroundColor Cyan
        Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CPU, @{Name='RAM_MB';Expression={[math]::Round($_.WorkingSet64/1MB,2)}}, StartTime | Format-Table
    }
    'force-start' {
        Start-Bot -Force $true
    }
    'supervisor' {
        Start-Supervisor
    }
}
