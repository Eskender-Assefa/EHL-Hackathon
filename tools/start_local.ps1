param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspacePath
# Only the named workspace cluster is started; no system PostgreSQL service.
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .local-postgres status | Out-Null
if ($LASTEXITCODE -ne 0) {
    & 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .local-postgres -l .local-postgres/server.log -o '-h 127.0.0.1 -p 55432' -w start
    if ($LASTEXITCODE -ne 0) { throw 'Workspace PostgreSQL failed to start.' }
}
# Verify the chosen port; choose another explicitly if occupied.
$portProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
try { $portProbe.Start() } catch { throw "Port $Port is occupied. Reuse the existing server or pass -Port with a free port." }
finally { $portProbe.Stop() }
$env:BMW_DATABASE_URL = 'postgresql://bmw_demo_app@127.0.0.1:55432/bmw_demo'
$env:BMW_DEV_PM = '1'
$env:BMW_APP_ORIGIN = "http://127.0.0.1:$Port"
$env:BMW_PORT = "$Port"
New-Item -ItemType Directory -Path reports -Force | Out-Null
$backendProcess = Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','backend' -WorkingDirectory $workspacePath -WindowStyle Hidden -RedirectStandardOutput 'reports/api.stdout.log' -RedirectStandardError 'reports/api.stderr.log' -PassThru
Write-Output "BMW workspace starting at http://127.0.0.1:$Port (launcher PID $($backendProcess.Id)); check /api/v1/health for database readiness."
