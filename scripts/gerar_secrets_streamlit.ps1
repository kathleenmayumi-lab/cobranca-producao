# Gera arquivo para colar no Streamlit Cloud → Settings → Secrets
# NÃO commite o arquivo gerado (já está no .gitignore)

$projectRoot = Split-Path $PSScriptRoot -Parent
$credsPath = Join-Path $projectRoot "credentials\service_account.json"
$outPath = Join-Path $projectRoot "streamlit_secrets_paste.toml"
$sheetId = "1n0BAsMRZqclQjEaDj_qOKqd0c5IM3uUreEfDcV-N3pU"

if (-not (Test-Path $credsPath)) {
    Write-Host "Arquivo não encontrado: $credsPath" -ForegroundColor Red
    exit 1
}

$jsonRaw = Get-Content $credsPath -Raw -Encoding UTF8
# Escapa aspas simples para TOML multilinha
$jsonEscaped = $jsonRaw.Trim().Replace("'", "''")

$content = @"
DASHBOARD_MODE = "cloud"

GOOGLE_SHEETS_ID = "$sheetId"

GOOGLE_SERVICE_ACCOUNT_JSON = '''
$jsonEscaped
'''
"@

Set-Content -Path $outPath -Value $content -Encoding UTF8

Write-Host ""
Write-Host "Arquivo gerado:" -ForegroundColor Green
Write-Host "  $outPath"
Write-Host ""
Write-Host "Próximo passo:" -ForegroundColor Cyan
Write-Host "  1. Abra o arquivo acima"
Write-Host "  2. Copie TUDO (Ctrl+A, Ctrl+C)"
Write-Host "  3. Cole em share.streamlit.io -> seu app -> Settings -> Secrets"
Write-Host ""

try {
    Set-Clipboard -Value (Get-Content $outPath -Raw)
    Write-Host "Conteúdo copiado para a área de transferência." -ForegroundColor Green
} catch {
    Write-Host "Copie manualmente do arquivo." -ForegroundColor Yellow
}
