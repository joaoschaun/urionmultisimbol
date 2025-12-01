@echo off
title Urion Trading Bot - Elite v2.0
color 0A

echo.
echo  ██╗   ██╗██████╗ ██╗ ██████╗ ███╗   ██╗
echo  ██║   ██║██╔══██╗██║██╔═══██╗████╗  ██║
echo  ██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║
echo  ██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║
echo  ╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║
echo   ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
echo.
echo  ELITE TRADING BOT v2.0
echo  ========================================
echo.

if "%1"=="" goto menu
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="status" goto status
if "%1"=="install" goto install
goto menu

:menu
echo  Selecione uma opcao:
echo.
echo  [1] Iniciar Bot
echo  [2] Parar Bot
echo  [3] Status
echo  [4] Instalar Dependencias
echo  [5] Abrir Dashboard
echo  [6] Sair
echo.
set /p choice="  Escolha: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto status
if "%choice%"=="4" goto install
if "%choice%"=="5" goto dashboard
if "%choice%"=="6" exit
goto menu

:start
echo.
echo  Iniciando Urion Bot...
echo.
call venv\Scripts\activate
python urion.py start
goto end

:stop
echo.
echo  Parando Urion Bot...
echo.
call venv\Scripts\activate
python urion.py stop
goto end

:status
echo.
echo  Verificando status...
echo.
call venv\Scripts\activate
python urion.py status
goto end

:install
echo.
echo  Instalando dependencias...
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado!
    goto end
)

REM Criar venv se nao existir
if not exist "venv" (
    echo  Criando ambiente virtual...
    python -m venv venv
)

REM Ativar e instalar dependencias Python
call venv\Scripts\activate
echo  Instalando pacotes Python...
pip install -r requirements.txt --quiet

REM Verificar Node.js para frontend
node --version >nul 2>&1
if errorlevel 1 (
    echo  [AVISO] Node.js nao encontrado. Frontend nao sera instalado.
    goto end
)

REM Instalar dependencias do frontend
if exist "frontend" (
    echo  Instalando pacotes do Frontend...
    cd frontend
    npm install --silent
    cd ..
)

echo.
echo  Instalacao concluida!
goto end

:dashboard
echo.
echo  Abrindo Dashboard...
start http://localhost:3000
goto end

:end
echo.
pause
