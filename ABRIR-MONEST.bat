@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\scripts\iniciar_monest.ps1"
pause
