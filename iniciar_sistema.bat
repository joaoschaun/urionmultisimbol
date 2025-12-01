@echo off
chcp 65001 > nul
title URION TRADING BOT - Sistema Integrado
color 0A

echo.
echo  ██╗   ██╗██████╗ ██╗ ██████╗ ███╗   ██╗
echo  ██║   ██║██╔══██╗██║██╔═══██╗████╗  ██║
echo  ██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║
echo  ██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║
echo  ╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║
echo   ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
echo.
echo   ELITE TRADING BOT v2.0 - SISTEMA INTEGRADO
echo   ============================================
echo.

cd /d C:\Users\Administrator\Desktop\urion

echo [1/4] Iniciando Backend API...
start "URION-Backend" /MIN cmd /c "cd /d C:\Users\Administrator\Desktop\urion && venv\Scripts\python.exe backend\server.py"
timeout /t 3 /nobreak > nul

echo [2/4] Iniciando Trading Engine...
start "URION-Trading" /MIN cmd /c "cd /d C:\Users\Administrator\Desktop\urion && venv\Scripts\python.exe main.py"
timeout /t 3 /nobreak > nul

echo [3/4] Iniciando Frontend...
start "URION-Frontend" /MIN cmd /c "cd /d C:\Users\Administrator\Desktop\urion\frontend && npm run dev"
timeout /t 3 /nobreak > nul

echo [4/4] Iniciando Monitor 24h...
start "URION-Monitor" /MIN cmd /c "cd /d C:\Users\Administrator\Desktop\urion && venv\Scripts\python.exe monitor_24h.py"
timeout /t 2 /nobreak > nul

echo.
echo   ============================================
echo   SISTEMA INICIADO COM SUCESSO!
echo   ============================================
echo.
echo   Dashboard: http://localhost:3000
echo   API: http://localhost:8080
echo.
echo   Abrindo dashboard no navegador...
timeout /t 2 /nobreak > nul
start http://localhost:3000

echo.
echo   Pressione qualquer tecla para PARAR todos os processos...
pause > nul

echo.
echo   Parando processos...
taskkill /F /FI "WINDOWTITLE eq URION-*" 2>nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo   Sistema encerrado.
pause
