# Expõe o dashboard na rede local (mesma Wi-Fi / VPN).
# Outras pessoas acessam: http://SEU_IP:8501

$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

$streamlit = Join-Path $projectRoot ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $streamlit)) {
    Write-Host "Ambiente virtual não encontrado. Rode: python -m venv .venv && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "Dashboard na rede local" -ForegroundColor Cyan
Write-Host "  Neste PC:     http://localhost:8501"
if ($ip) {
    Write-Host "  Outros PCs:   http://${ip}:8501" -ForegroundColor Green
} else {
    Write-Host "  Outros PCs:   http://SEU_IP_LOCAL:8501" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Mantenha este terminal aberto. Ctrl+C para encerrar." -ForegroundColor DarkGray
Write-Host ""

& $streamlit run dashboard\app.py `
    --server.address 0.0.0.0 `
    --server.port 8501 `
    --server.headless true
