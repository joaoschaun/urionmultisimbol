@echo off
:: ============================================
:: URION Trading Bot - Advanced Launcher
:: ============================================

setlocal enabledelayedexpansion
title Urion Trading Bot - Launcher

:MENU
cls
color 0B
echo.
echo ╔════════════════════════════════════════════╗
echo ║     URION TRADING BOT - LAUNCHER          ║
echo ╚════════════════════════════════════════════╝
echo.
echo  1. Iniciar Bot (com VENV)
echo  2. Verificar Status do Sistema
echo  3. Ver Logs em Tempo Real
echo  4. Parar Bot
echo  5. Instalar/Atualizar Dependencias
echo  6. Abrir Dashboard Web
echo  7. Sair
echo.
echo ============================================
echo.

set /p opcao="Escolha uma opcao (1-7): "

if "%opcao%"=="1" goto INICIAR_BOT
if "%opcao%"=="2" goto VERIFICAR_STATUS
if "%opcao%"=="3" goto VER_LOGS
if "%opcao%"=="4" goto PARAR_BOT
if "%opcao%"=="5" goto INSTALAR_DEPS
if "%opcao%"=="6" goto DASHBOARD
if "%opcao%"=="7" goto SAIR

echo.
color 0C
echo [ERRO] Opcao invalida!
timeout /t 2 >nul
goto MENU

:INICIAR_BOT
cls
color 0A
echo.
echo ════════════════════════════════════════════
echo    INICIANDO BOT
echo ════════════════════════════════════════════
echo.

:: Verificar venv
if not exist "venv\Scripts\activate.bat" (
    color 0E
    echo [AVISO] Ambiente virtual nao encontrado!
    echo.
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo [ERRO] Falha ao criar venv
        pause
        goto MENU
    )
    echo [OK] Venv criado com sucesso!
)

echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

if errorlevel 1 (
    color 0C
    echo [ERRO] Falha ao ativar venv
    pause
    goto MENU
)

echo [OK] Venv ativado!
echo.

:: Verificar dependências
echo [INFO] Verificando dependencias...
python -c "import MetaTrader5" 2>nul
if errorlevel 1 (
    color 0E
    echo [AVISO] Dependencias nao instaladas
    echo.
    set /p instalar="Instalar agora? (S/N): "
    if /i "!instalar!"=="S" (
        goto INSTALAR_DEPS
    ) else (
        goto MENU
    )
)

echo [OK] Dependencias OK
echo.

:: Iniciar bot
echo ════════════════════════════════════════════
echo    BOT INICIANDO...
echo ════════════════════════════════════════════
echo.
echo Pressione Ctrl+C para parar
echo.

python src\main.py

echo.
color 0E
echo ════════════════════════════════════════════
echo    BOT ENCERRADO
echo ════════════════════════════════════════════
echo.
pause
goto MENU

:VERIFICAR_STATUS
cls
color 0B
echo.
echo ════════════════════════════════════════════
echo    STATUS DO SISTEMA
echo ════════════════════════════════════════════
echo.

:: Verificar venv
if exist "venv\Scripts\activate.bat" (
    echo [OK] Ambiente virtual: INSTALADO
) else (
    echo [X] Ambiente virtual: NAO INSTALADO
)

:: Verificar Python no venv
if exist "venv\Scripts\python.exe" (
    echo [OK] Python venv: ENCONTRADO
    call venv\Scripts\activate.bat >nul 2>&1
    for /f "delims=" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo     Versao: !PYTHON_VERSION!
) else (
    echo [X] Python venv: NAO ENCONTRADO
)

echo.

:: Verificar arquivos principais
if exist "src\main.py" (
    echo [OK] main.py: ENCONTRADO
) else (
    echo [X] main.py: NAO ENCONTRADO
)

if exist "config\config.yaml" (
    echo [OK] config.yaml: ENCONTRADO
) else (
    echo [X] config.yaml: NAO ENCONTRADO
)

if exist ".env" (
    echo [OK] .env: ENCONTRADO
) else (
    echo [X] .env: NAO ENCONTRADO
)

echo.

:: Verificar processos Python
echo [INFO] Verificando processos Python...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if errorlevel 1 (
    echo [INFO] Bot: NAO ESTA RODANDO
) else (
    echo [OK] Bot: RODANDO
)

echo.
echo ════════════════════════════════════════════
pause
goto MENU

:VER_LOGS
cls
color 0E
echo.
echo ════════════════════════════════════════════
echo    LOGS EM TEMPO REAL
echo ════════════════════════════════════════════
echo.
echo Pressione Ctrl+C para voltar ao menu
echo.

if exist "logs\urion.log" (
    powershell -Command "Get-Content logs\urion.log -Wait -Tail 50"
) else (
    echo [AVISO] Arquivo de log nao encontrado
    echo.
    echo Execute o bot primeiro para gerar logs
    pause
)

goto MENU

:PARAR_BOT
cls
color 0C
echo.
echo ════════════════════════════════════════════
echo    PARANDO BOT
echo ════════════════════════════════════════════
echo.

taskkill /F /IM python.exe 2>nul
if errorlevel 1 (
    echo [INFO] Nenhum processo Python encontrado
) else (
    echo [OK] Processos Python encerrados
)

echo.
pause
goto MENU

:INSTALAR_DEPS
cls
color 0B
echo.
echo ════════════════════════════════════════════
echo    INSTALANDO DEPENDENCIAS
echo ════════════════════════════════════════════
echo.

:: Ativar venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    color 0C
    echo [ERRO] Venv nao encontrado!
    echo.
    echo Execute opcao 1 primeiro para criar o venv
    pause
    goto MENU
)

:: Atualizar pip
echo [INFO] Atualizando pip...
python -m pip install --upgrade pip setuptools wheel

echo.
echo [INFO] Instalando dependencias do requirements.txt...
pip install -r requirements.txt

if errorlevel 1 (
    color 0E
    echo.
    echo [AVISO] Algumas dependencias podem ter falHado
    echo.
) else (
    color 0A
    echo.
    echo [OK] Dependencias instaladas com sucesso!
    echo.
)

pause
goto MENU

:DASHBOARD
cls
color 0D
echo.
echo ════════════════════════════════════════════
echo    ABRINDO DASHBOARD WEB
echo ════════════════════════════════════════════
echo.

:: Ativar venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    color 0C
    echo [ERRO] Venv nao encontrado!
    pause
    goto MENU
)

:: Verificar se dashboard existe
if exist "dashboard_web.py" (
    echo [INFO] Iniciando dashboard...
    echo.
    echo Dashboard estara disponivel em: http://localhost:8050
    echo.
    echo Pressione Ctrl+C para parar
    echo.
    start http://localhost:8050
    python dashboard_web.py
) else (
    color 0E
    echo [AVISO] Dashboard nao encontrado
    echo.
    echo Arquivo dashboard_web.py nao existe
    pause
)

goto MENU

:SAIR
cls
color 0A
echo.
echo ════════════════════════════════════════════
echo    ENCERRANDO
echo ════════════════════════════════════════════
echo.
echo Obrigado por usar o Urion Trading Bot!
echo.
timeout /t 2 >nul
exit

