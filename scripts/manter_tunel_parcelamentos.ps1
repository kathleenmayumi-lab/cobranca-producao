# Garante tunel publico do app Parcelamentos (8503) via Cloudflare.
param(
    [switch]$ForceRestart
)

$ErrorActionPreference = "Continue"
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

$logFile = Join-Path $projectRoot "data\tunel_parcelamentos_watchdog.log"
$startScript = Join-Path $projectRoot "scripts\iniciar_tunel_parcelamentos.ps1"
$linkFile = Join-Path $projectRoot "data\parcelamentos_link_publico.txt"
$port = 8503

function Write-Log {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    $dir = Split-Path $logFile -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-Local {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:${port}/" -UseBasicParsing -TimeoutSec 8
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Get-SavedUrl {
    if (-not (Test-Path $linkFile)) { return $null }
    $m = Select-String -Path $linkFile -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
    if ($m) { return $m.Matches[0].Value }
    return $null
}

function Test-Public([string]$Url) {
    if (-not $Url) { return $false }
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Stop-ParcelamentosTunnel {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match 'cloudflared|powershell' -and
            $_.CommandLine -match 'iniciar_tunel_parcelamentos|tunnel --url http://127\.0\.0\.1:8503'
        } |
        ForEach-Object {
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
        }
}

if (-not (Test-Local)) {
    Write-Log "App 8503 fora - subindo parcelamentos"
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $projectRoot "scripts\iniciar_parcelamentos.ps1")
    ) -WindowStyle Minimized
    Start-Sleep -Seconds 8
}

if ($ForceRestart) {
    Write-Log "Reinicio forcado do tunel parcelamentos"
    Stop-ParcelamentosTunnel
    Start-Sleep -Seconds 2
}

$url = Get-SavedUrl
if ((-not $ForceRestart) -and (Test-Public $url)) {
    Write-Log "OK: tunel parcelamentos saudavel ($url)"
    exit 0
}

Write-Log "Iniciando tunel parcelamentos"
Stop-ParcelamentosTunnel
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", $startScript
) -WindowStyle Minimized

Start-Sleep -Seconds 12
$url = Get-SavedUrl
if (Test-Public $url) {
    Write-Log "OK: tunel parcelamentos recuperado ($url)"
    exit 0
}
Write-Log "AVISO: tunel iniciou, mas URL ainda nao respondeu 200 (veja $linkFile / log)"
exit 1
