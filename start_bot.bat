@echo off
REM ============================================
REM URION Trading Bot - Launcher
REM ============================================

title Urion Trading Bot

echo.
echo ============================================
echo    URION TRADING BOT - LAUNCHER
echo ============================================
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale Python 3.11+ primeiro.
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.

REM Verificar se ambiente virtual existe
if not exist "venv\Scripts\activate.bat" (
    echo [AVISO] Ambiente virtual nao encontrado
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado
    echo.
)

REM Ativar ambiente virtual
echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Falha ao ativar ambiente virtual
    pause
    exit /b 1
)
echo [OK] Ambiente virtual ativado
echo.

REM Verificar dependências
echo [INFO] Verificando dependencias...
python -c "import MetaTrader5" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Dependencias nao instaladas
    echo Instalando dependencias...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas
    echo.
)

echo [OK] Dependencias OK
echo.

REM Verificar arquivo .env
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado!
    echo Copiando .env.example para .env...
    copy .env.example .env >nul
    echo.
    echo ============================================
    echo  CONFIGURE SUAS CREDENCIAIS NO .env
    echo ============================================
    echo.
    echo Abra o arquivo .env e configure:
    echo   - MT5_LOGIN
    echo   - MT5_PASSWORD
    echo   - MT5_SERVER
    echo   - MT5_PATH
    echo   - TELEGRAM_BOT_TOKEN
    echo   - TELEGRAM_CHAT_ID
    echo.
    echo Pressione qualquer tecla para abrir .env...
    pause >nul
    notepad .env
    echo.
    echo Apos configurar, execute este arquivo novamente.
    echo.
    pause
    exit /b 0
)

echo [OK] Arquivo .env encontrado
echo.

REM Menu principal
:menu
cls
echo.
echo ============================================
echo    URION TRADING BOT - MENU
echo ============================================
echo.
echo 1. Verificar Setup
echo 2. Executar Bot
echo 3. Ver Logs (Tempo Real)
echo 4. Editar Configuracoes
echo 5. Editar Credenciais (.env)
echo 6. Sair
echo.
set /p choice="Escolha uma opcao (1-6): "

if "%choice%"=="1" goto verify
if "%choice%"=="2" goto run
if "%choice%"=="3" goto logs
if "%choice%"=="4" goto config
if "%choice%"=="5" goto env
if "%choice%"=="6" goto end
goto menu

:verify
cls
echo.
echo ============================================
echo    VERIFICANDO SETUP
echo ============================================
echo.
python verify_setup.py
echo.
pause
goto menu

:run
cls
echo.
echo ============================================
echo    EXECUTANDO BOT
echo ============================================
echo.
echo [INFO] Bot iniciando...
echo [INFO] Pressione Ctrl+C para parar
echo.
python main.py
echo.
echo [INFO] Bot encerrado
pause
goto menu

:logs
cls
echo.
echo ============================================
echo    LOGS EM TEMPO REAL
echo ============================================
echo.
echo [INFO] Pressione Ctrl+C para voltar ao menu
echo.
if exist "logs\urion.log" (
    powershell -Command "Get-Content logs\urion.log -Wait -Tail 50"
) else (
    echo [AVISO] Arquivo de log nao encontrado
    echo Execute o bot primeiro para gerar logs
    pause
)
goto menu

:config
cls
echo.
echo ============================================
echo    EDITANDO CONFIGURACOES
echo ============================================
echo.
if exist "config\config.yaml" (
    notepad config\config.yaml
) else (
    echo [ERRO] Arquivo config.yaml nao encontrado
    pause
)
goto menu

:env
cls
echo.
echo ============================================
echo    EDITANDO CREDENCIAIS
echo ============================================
echo.
if exist ".env" (
    notepad .env
) else (
    echo [ERRO] Arquivo .env nao encontrado
    pause
)
goto menu

:end
cls
echo.
echo ============================================
echo    ENCERRANDO
echo ============================================
echo.
echo Obrigado por usar o Urion Trading Bot!
echo.
timeout /t 2 >nul
exit /b 0
