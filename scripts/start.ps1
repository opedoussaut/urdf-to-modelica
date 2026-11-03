<#
Starts HT GEN7 PhysAI Studio (Engineering-Grounded Physical AI) reliably (local only).

  2. Checks the local Ollama server (127.0.0.1:11434); the copilot is unavailable without it, the rest still works.
  3. Builds the web UI when sources are newer than web/dist (or always with -Build).
  4. Starts the FastAPI server on 127.0.0.1:8000; restarts it when Python sources changed since it started
     (or with -Restart), waits for /api/health and prints a service summary.

Usage:  scripts\start.ps1 [-Restart] [-Build] [-NoBuild] [-NoBrowser]
#>
param([switch]$Restart, [switch]$Build, [switch]$NoBuild, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Python environment missing: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt' }

function Test-Url($url, $timeout = 3) {
    try { Invoke-WebRequest -UseBasicParsing $url -TimeoutSec $timeout | Out-Null; return $true } catch { return $false }
}
function Wait-Url($url, $seconds) {
    for ($i = 0; $i -lt $seconds; $i += 2) { if (Test-Url $url) { return $true }; Start-Sleep -Seconds 2 }
    return $false
}

# 2. Ollama (never started or configured here; local loopback only)
if (Test-Url 'http://127.0.0.1:11434/api/version') { Write-Host '[ollama] running on 127.0.0.1:11434' }
else { Write-Warning '[ollama] not reachable on 127.0.0.1:11434 - start the Ollama app for the copilot' }

# 3. Web UI build
$web = Join-Path $root 'web'
$dist = Join-Path $web 'dist\index.html'
$needBuild = $Build -or -not (Test-Path $dist)
if (-not $needBuild -and -not $NoBuild) {
    $built = (Get-Item $dist).LastWriteTimeUtc
    $newest = Get-ChildItem (Join-Path $web 'src'), (Join-Path $web 'index.html'), (Join-Path $web 'package.json') -Recurse -File |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    $needBuild = $newest.LastWriteTimeUtc -gt $built
}
if ($needBuild -and -not $NoBuild) {
    Write-Host '[web] building UI ...'
    Push-Location $web
    try {
        if (-not (Test-Path 'node_modules')) { npm ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' } }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
} else { Write-Host '[web] build up to date' }

# 4. API server
$servers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'kkh\.api\.main' })
if ($servers.Count -gt 0 -and -not $Restart) {
    $started = ($servers | ForEach-Object { $_.CreationDate } | Sort-Object | Select-Object -First 1)
    $newestPy = Get-ChildItem (Join-Path $root 'kkh') -Recurse -Filter *.py -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($newestPy.LastWriteTime -gt $started) {
        Write-Host "[api] Python sources changed since the server started ($($newestPy.Name)); restarting"
        $Restart = $true
    }
}
if ($Restart -and $servers.Count -gt 0) {
    $servers | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
    Start-Sleep -Seconds 1
    $servers = @()
}
if ($servers.Count -eq 0) {
    $logs = Join-Path $root 'runs\studio'
    New-Item -ItemType Directory -Force $logs | Out-Null
    $p = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'kkh.api.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs 'stdout.log') -RedirectStandardError (Join-Path $logs 'stderr.log')
    Write-Host "[api] starting (pid $($p.Id)), logs in runs\studio"
}
if (-not (Wait-Url 'http://127.0.0.1:8000/api/health' 60)) { throw '[api] not healthy after 60 s - see runs\studio\stderr.log' }
$health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 20
Write-Host ("[status] Ollama: {0} | OpenModelica installed: {1}" -f `
    $(if ($health.ollama.ok) { "$($health.ollama.models.Count) local models" } else { 'unavailable' }),
    $health.openmodelica.installed)
Write-Host 'HT GEN7 PhysAI Studio ready: http://127.0.0.1:8000'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8000' }
