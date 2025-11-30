@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ================================================================================
:: URION TRADING BOT - CONTROLE COMPLETO
:: Virtus Investimentos
:: ================================================================================

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
set "MAIN_SCRIPT=%SCRIPT_DIR%src\main.py"
set "SUPERVISOR_SCRIPT=%SCRIPT_DIR%supervisor.py"
set "PID_FILE=%SCRIPT_DIR%urion_bot.pid"
set "LOG_FILE=%SCRIPT_DIR%logs\urion.log"

:: Cores para o Windows
set "COLOR_GREEN=[92m"
set "COLOR_RED=[91m"
set "COLOR_YELLOW=[93m"
set "COLOR_BLUE=[94m"
set "COLOR_RESET=[0m"

:: ================================================================================
:: MENU PRINCIPAL
:: ================================================================================

:menu
cls
echo.
echo %COLOR_BLUE%================================================================================
echo URION TRADING BOT - PAINEL DE CONTROLE
echo ================================================================================%COLOR_RESET%
echo.
echo %COLOR_YELLOW%[1]%COLOR_RESET% Status do Bot
echo %COLOR_YELLOW%[2]%COLOR_RESET% Iniciar Bot
echo %COLOR_YELLOW%[3]%COLOR_RESET% Iniciar Bot (Forcar reinicio)
echo %COLOR_YELLOW%[4]%COLOR_RESET% Parar Bot
echo %COLOR_YELLOW%[5]%COLOR_RESET% Reiniciar Bot
echo %COLOR_YELLOW%[6]%COLOR_RESET% Iniciar com Supervisor (Auto-restart)
echo %COLOR_YELLOW%[7]%COLOR_RESET% Ver Logs (ultimas 30 linhas)
echo %COLOR_YELLOW%[8]%COLOR_RESET% Limpar Processos Zumbis
echo %COLOR_YELLOW%[9]%COLOR_RESET% Sair
echo.
set /p "choice=%COLOR_GREEN%Escolha uma opcao:%COLOR_RESET% "

if "%choice%"=="1" goto status
if "%choice%"=="2" goto start
if "%choice%"=="3" goto force_start
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto restart
if "%choice%"=="6" goto supervisor
if "%choice%"=="7" goto logs
if "%choice%"=="8" goto cleanup
if "%choice%"=="9" goto end

echo %COLOR_RED%Opcao invalida!%COLOR_RESET%
timeout /t 2 >nul
goto menu

:: ================================================================================
:: STATUS
:: ================================================================================

:status
cls
echo %COLOR_BLUE%================================================================================
echo STATUS DO BOT
echo ================================================================================%COLOR_RESET%
echo.

if not exist "%PID_FILE%" (
    echo %COLOR_RED%BOT NAO ESTA RODANDO%COLOR_RESET%
    echo.
    goto show_python_processes
)

set /p PID=<"%PID_FILE%"
tasklist /FI "PID eq %PID%" 2>nul | find /I "python.exe" >nul

if errorlevel 1 (
    echo %COLOR_RED%BOT NAO ESTA RODANDO (PID file existe mas processo nao)%COLOR_RESET%
    echo Limpando PID file...
    del "%PID_FILE%" 2>nul
    echo.
    goto show_python_processes
)

echo %COLOR_GREEN%BOT ESTA RODANDO%COLOR_RESET%
echo.
echo PID: %PID%

:: Obter informacoes do processo usando WMIC
for /f "tokens=2 delims==" %%i in ('wmic process where "ProcessId=%PID%" get WorkingSetSize /value 2^>nul') do set "MEM=%%i"
for /f "tokens=2 delims==" %%i in ('wmic process where "ProcessId=%PID%" get ThreadCount /value 2^>nul') do set "THREADS=%%i"

if defined MEM (
    set /a "MEM_MB=!MEM! / 1024 / 1024"
    echo Memoria: !MEM_MB! MB
)
if defined THREADS (
    echo Threads: !THREADS!
)

echo.

:show_python_processes
echo %COLOR_YELLOW%Processos Python ativos:%COLOR_RESET%
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe"
if errorlevel 1 (
    echo Nenhum processo Python encontrado
)

echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: START
:: ================================================================================

:start
cls
echo %COLOR_BLUE%================================================================================
echo INICIANDO BOT
echo ================================================================================%COLOR_RESET%
echo.

if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    tasklist /FI "PID eq !PID!" 2>nul | find /I "python.exe" >nul
    if not errorlevel 1 (
        echo %COLOR_RED%Bot ja esta rodando (PID: !PID!)%COLOR_RESET%
        echo Use a opcao 3 para forcar reinicio ou opcao 5 para reiniciar.
        echo.
        echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
        pause >nul
        goto menu
    )
)

echo Iniciando bot em background...
start /B "" "%VENV_PYTHON%" "%MAIN_SCRIPT%" >nul 2>&1

timeout /t 3 >nul

echo %COLOR_GREEN%Bot iniciado!%COLOR_RESET%
echo Aguarde alguns segundos para inicializacao completa.
echo Use a opcao 1 para verificar o status.
echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: FORCE START
:: ================================================================================

:force_start
cls
echo %COLOR_BLUE%================================================================================
echo FORCANDO REINICIO DO BOT
echo ================================================================================%COLOR_RESET%
echo.

echo Parando bot existente...
call :stop_bot_internal

echo.
echo Iniciando bot com flag --force...
start /B "" "%VENV_PYTHON%" "%MAIN_SCRIPT%" --force >nul 2>&1

timeout /t 3 >nul

echo %COLOR_GREEN%Bot forcado a reiniciar!%COLOR_RESET%
echo Use a opcao 1 para verificar o status.
echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: STOP
:: ================================================================================

:stop
cls
echo %COLOR_BLUE%================================================================================
echo PARANDO BOT
echo ================================================================================%COLOR_RESET%
echo.

call :stop_bot_internal

echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:stop_bot_internal
if not exist "%PID_FILE%" (
    echo %COLOR_RED%Bot nao esta rodando%COLOR_RESET%
    goto :eof
)

set /p PID=<"%PID_FILE%"
echo Enviando sinal de parada para PID %PID%...

taskkill /PID %PID% 2>nul
if errorlevel 1 (
    echo %COLOR_RED%Processo nao encontrado ou ja finalizado%COLOR_RESET%
) else (
    echo Aguardando finalizacao graceful (10 segundos)...
    timeout /t 10 >nul
    
    tasklist /FI "PID eq %PID%" 2>nul | find /I "python.exe" >nul
    if not errorlevel 1 (
        echo Processo ainda ativo, forcando finalizacao...
        taskkill /F /PID %PID% 2>nul
    )
    
    echo %COLOR_GREEN%Bot parado!%COLOR_RESET%
)

if exist "%PID_FILE%" (
    del "%PID_FILE%" 2>nul
)
goto :eof

:: ================================================================================
:: RESTART
:: ================================================================================

:restart
cls
echo %COLOR_BLUE%================================================================================
echo REINICIANDO BOT
echo ================================================================================%COLOR_RESET%
echo.

echo Parando bot...
call :stop_bot_internal

echo.
echo Aguardando 5 segundos...
timeout /t 5 >nul

echo.
echo Iniciando bot...
start /B "" "%VENV_PYTHON%" "%MAIN_SCRIPT%" >nul 2>&1

timeout /t 3 >nul

echo %COLOR_GREEN%Bot reiniciado!%COLOR_RESET%
echo Use a opcao 1 para verificar o status.
echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: SUPERVISOR
:: ================================================================================

:supervisor
cls
echo %COLOR_BLUE%================================================================================
echo INICIANDO BOT COM SUPERVISOR (AUTO-RESTART)
echo ================================================================================%COLOR_RESET%
echo.

echo %COLOR_YELLOW%ATENCAO:%COLOR_RESET%
echo O supervisor mantera o bot rodando e reiniciara automaticamente em caso de falha.
echo Para parar, use Ctrl+C ou feche esta janela, depois use a opcao 4 para garantir parada.
echo.
echo Limite de falhas: 5 falhas consecutivas em 5 minutos
echo Delay entre restarts: 10 segundos
echo.
echo Iniciando supervisor...
echo.

"%VENV_PYTHON%" "%SUPERVISOR_SCRIPT%"

echo.
echo %COLOR_YELLOW%Supervisor finalizado.%COLOR_RESET%
echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: LOGS
:: ================================================================================

:logs
cls
echo %COLOR_BLUE%================================================================================
echo ULTIMAS 30 LINHAS DO LOG
echo ================================================================================%COLOR_RESET%
echo.

if not exist "%LOG_FILE%" (
    echo %COLOR_RED%Arquivo de log nao encontrado!%COLOR_RESET%
    echo.
    echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
    pause >nul
    goto menu
)

powershell -Command "Get-Content '%LOG_FILE%' -Tail 30"

echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: CLEANUP
:: ================================================================================

:cleanup
cls
echo %COLOR_BLUE%================================================================================
echo LIMPANDO PROCESSOS ZUMBIS
echo ================================================================================%COLOR_RESET%
echo.

echo %COLOR_YELLOW%ATENCAO:%COLOR_RESET%
echo Esta operacao encerrara TODOS os processos Python.
echo Se voce tem outros scripts Python rodando, eles serao afetados.
echo.
set /p "confirm=Deseja continuar? (S/N): "

if /I not "%confirm%"=="S" (
    echo Operacao cancelada.
    echo.
    echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
    pause >nul
    goto menu
)

echo.
echo Encerrando processos Python...

taskkill /F /IM python.exe 2>nul
if errorlevel 1 (
    echo %COLOR_YELLOW%Nenhum processo Python encontrado.%COLOR_RESET%
) else (
    echo %COLOR_GREEN%Processos encerrados!%COLOR_RESET%
)

if exist "%PID_FILE%" (
    echo Removendo PID file...
    del "%PID_FILE%" 2>nul
)

echo.
echo %COLOR_GREEN%Limpeza concluida!%COLOR_RESET%
echo.
echo %COLOR_YELLOW%Pressione qualquer tecla para voltar ao menu...%COLOR_RESET%
pause >nul
goto menu

:: ================================================================================
:: END
:: ================================================================================

:end
cls
echo.
echo %COLOR_GREEN%Ate logo!%COLOR_RESET%
echo.
timeout /t 2 >nul
exit /b 0
