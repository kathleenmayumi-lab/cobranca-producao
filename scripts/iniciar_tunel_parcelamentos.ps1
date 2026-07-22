# Expoe o app de Parcelamentos (porta 8503) com URL HTTPS publica via Cloudflare Tunnel.
# Nao conflita com o ngrok fixo do painel (8501).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\scripts\iniciar_tunel_parcelamentos.ps1

param(
    [int]$Port = 8503,
    [string]$CloudflaredPath = ""
)

$ErrorActionPreference = "Continue"
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

$linkFile = Join-Path $projectRoot "data\parcelamentos_link_publico.txt"
$logFile = Join-Path $projectRoot "data\tunel_parcelamentos.log"
$healthUrl = "http://127.0.0.1:${Port}/"

function Write-Log {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    $dir = Split-Path $logFile -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Resolve-Cloudflared {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path $Preferred)) {
        return (Resolve-Path $Preferred).Path
    }
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    foreach ($path in @(
            "$env:ProgramFiles\cloudflared\cloudflared.exe",
            "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
        )) {
        if (Test-Path $path) {
            return $path
        }
    }
    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path $wingetRoot) {
        $found = Get-ChildItem -Path $wingetRoot -Filter "cloudflared.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($found) {
            return $found
        }
    }
    return $null
}

function Test-AppUp {
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 8
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Save-PublicLink {
    param([string]$PublicUrl)
    $stamp = Get-Date -Format "dd/MM/yyyy HH:mm:ss"
    $ip = "172.16.30.37"
    try {
        $detected = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -like "172.*" -or $_.IPAddress -like "192.168.*" } |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($detected) { $ip = $detected }
    } catch { }
    $content = @(
        "Atualizado: $stamp"
        ""
        "PARCELAMENTOS (Over 90 / IR) - link publico:"
        "  $PublicUrl"
        ""
        "Rede local:"
        "  http://${ip}:${Port}/"
        ""
        "Neste PC:"
        "  http://127.0.0.1:${Port}/"
        ""
        "Obs: URL Cloudflare muda se o tunel reiniciar. Processo precisa ficar aberto."
    ) -join "`r`n"
    $dir = Split-Path $linkFile -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -Path $linkFile -Value $content -Encoding UTF8
    Write-Host ""
    Write-Host ">>> LINK PARA A EQUIPE:" -ForegroundColor Green
    Write-Host ">>> $PublicUrl" -ForegroundColor Green
    Write-Host ">>> (salvo em data\parcelamentos_link_publico.txt)" -ForegroundColor DarkGray
    Write-Host ""
}

$cloudflared = Resolve-Cloudflared -Preferred $CloudflaredPath
if (-not $cloudflared) {
    Write-Host "cloudflared nao encontrado. Instale: winget install --id Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}

if (-not (Test-AppUp)) {
    Write-Host "App parcelamentos nao responde em $healthUrl" -ForegroundColor Red
    Write-Host "Suba: powershell -ExecutionPolicy Bypass -File .\scripts\iniciar_parcelamentos.ps1"
    exit 1
}

Write-Log "Iniciando tunel Cloudflare ($cloudflared) -> $healthUrl"
Write-Host ""
Write-Host "=== Tunel PARCELAMENTOS (HTTPS publico) ===" -ForegroundColor Cyan
Write-Host "  Mantendo este terminal aberto. Ctrl+C encerra o tunel." -ForegroundColor DarkGray
Write-Host ""

$urlSaved = $false
& $cloudflared tunnel --url $healthUrl --no-autoupdate 2>&1 | ForEach-Object {
    $line = "$_"
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
    if (-not $urlSaved -and $line -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
        $publicUrl = $Matches[1].TrimEnd('/') + '/'
        Save-PublicLink -PublicUrl $publicUrl
        $urlSaved = $true
    }
}

Write-Log "Tunel parcelamentos encerrado."
