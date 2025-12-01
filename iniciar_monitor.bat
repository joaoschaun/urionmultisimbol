@echo off
chcp 65001 > nul
title URION - Monitor 24 Horas
color 0A

echo.
echo ============================================================
echo   URION TRADING BOT - MONITOR 24 HORAS
echo ============================================================
echo.
echo   Este monitor irá acompanhar o bot por 24 horas
echo   verificando todos os módulos e operações.
echo.
echo   Logs serão salvos em: logs\monitor_24h.log
echo   Relatório JSON em: logs\monitor_report.json
echo.
echo ============================================================
echo.
echo Iniciando monitoramento...
echo.

cd /d C:\Users\Administrator\Desktop\urion
.\venv\Scripts\python.exe monitor_24h.py

echo.
echo Monitoramento finalizado!
pause
