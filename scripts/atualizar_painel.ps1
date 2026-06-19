# Atualiza snapshot local + planilha Google com improdutivas
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "ERRO: .venv nao encontrado. Rode: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Write-Host "=== Atualizando painel de cobranca ===" -ForegroundColor Cyan
& $python run.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "=== Verificando improdutivas no snapshot ===" -ForegroundColor Cyan
& $python scripts\test_improdutivas.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$testFile = Join-Path $PWD "data\test_improdutivas.json"
if (Test-Path $testFile) {
    Get-Content $testFile -Raw | Write-Host
}

Write-Host ""
Write-Host "OK. Agora: git push + Reboot no Streamlit Cloud + Recarregar no painel." -ForegroundColor Green
