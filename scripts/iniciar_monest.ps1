$projectRoot = "C:\Users\usuario\Projects\cobranca-producao"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$streamlit = Join-Path $projectRoot ".venv\Scripts\streamlit.exe"
$port = 8504

Set-Location $projectRoot
Remove-Item Env:VIEWER_READONLY -ErrorAction SilentlyContinue

if (-not (Test-Path $streamlit)) {
    Write-Host "Instalando dependencias..." -ForegroundColor Yellow
    & $python -m pip install -r requirements.txt
}

Write-Host "Monest (base de acordos) em http://127.0.0.1:$port" -ForegroundColor Green
Write-Host "App apartado do painel de producao (8501/8502) e dos parcelamentos (8503)." -ForegroundColor DarkGray

& $streamlit run dashboard\monest_app.py `
    --server.port $port `
    --server.headless true `
    --server.address 0.0.0.0
