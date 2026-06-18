$projectRoot = "C:\Users\usuario\Projects\cobranca-producao"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$streamlit = Join-Path $projectRoot ".venv\Scripts\streamlit.exe"

Set-Location $projectRoot

if (-not (Test-Path $streamlit)) {
    Write-Host "Instalando dependencias do dashboard..." -ForegroundColor Yellow
    & $python -m pip install -r requirements.txt
}

Write-Host "Abrindo dashboard em http://localhost:8501" -ForegroundColor Green
& $streamlit run dashboard\app.py --server.headless true
