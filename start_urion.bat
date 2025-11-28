@echo off
:: ============================================
:: URION Trading Bot - Launcher with VENV
:: ============================================

setlocal enabledelayedexpansion
title Urion Trading Bot

:: Cores (Windows 10+)
color 0A

echo.
echo ============================================
echo    URION TRADING BOT
echo ============================================
echo.

:: Verificar se venv existe
if not exist "venv\Scripts\activate.bat" (
    color 0C
    echo [ERRO] Ambiente virtual nao encontrado!
    echo.
    echo Execute primeiro: python -m venv venv
    echo.
    pause
    exit /b 1
)

echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

if errorlevel 1 (
    color 0C
    echo [ERRO] Falha ao ativar ambiente virtual
    pause
    exit /b 1
)

echo [OK] Ambiente virtual ativado!
echo.

:: Verificar se Python existe no venv
where python >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERRO] Python nao encontrado no venv
    pause
    exit /b 1
)

echo [INFO] Python: 
python --version
echo.

:: Verificar se main.py existe
if not exist "src\main.py" (
    color 0C
    echo [ERRO] Arquivo src\main.py nao encontrado!
    pause
    exit /b 1
)

echo ============================================
echo    INICIANDO BOT...
echo ============================================
echo.
echo Pressione Ctrl+C para parar o bot
echo.

:: Iniciar bot
python src\main.py

:: Se o bot parar
echo.
echo ============================================
echo    BOT ENCERRADO
echo ============================================
echo.

pause
