@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\scripts\iniciar_parcelamentos.ps1"
pause
