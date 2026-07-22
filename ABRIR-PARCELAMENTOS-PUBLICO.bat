@echo off
cd /d "%~dp0"
echo Subindo app Parcelamentos (8503) + tunel publico...
powershell -ExecutionPolicy Bypass -File ".\scripts\manter_tunel_parcelamentos.ps1" -ForceRestart
echo.
echo Link salvo em: data\parcelamentos_link_publico.txt
type "data\parcelamentos_link_publico.txt" 2>nul
pause
