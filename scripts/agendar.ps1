$projectRoot = "C:\Users\usuario\Projects\cobranca-producao"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$script = Join-Path $projectRoot "run.py"
$taskName = "CobrancaProducao30Min"

if (-not (Test-Path $python)) {
    Write-Host "Ambiente virtual nao encontrado. Rode primeiro:" -ForegroundColor Yellow
    Write-Host "  cd $projectRoot"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(8) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 12)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "Tarefa '$taskName' criada: executa a cada 30 min (08h-20h)." -ForegroundColor Green
Write-Host "Para testar agora: Start-ScheduledTask -TaskName $taskName"
