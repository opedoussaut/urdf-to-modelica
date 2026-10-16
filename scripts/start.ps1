param([switch]$NoBuild)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $NoBuild) {
    Push-Location (Join-Path $root 'web')
    try {
        if (-not (Test-Path 'node_modules')) { npm ci --no-audit --no-fund }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
}
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Install requirements into .venv first (see README.md)' }
try {
    Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/studio' -TimeoutSec 2 | Out-Null
    Write-Host 'Studio already available at http://127.0.0.1:8000'
    exit 0
} catch {}
$logs = Join-Path $root 'runs\studio'
New-Item -ItemType Directory -Force $logs | Out-Null
$process = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','kkh.api.main:app','--host','127.0.0.1','--port','8000') `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logs 'stdout.log') -RedirectStandardError (Join-Path $logs 'stderr.log')
Write-Host "Studio starting at http://127.0.0.1:8000 (pid $($process.Id)). Logs: $logs"
