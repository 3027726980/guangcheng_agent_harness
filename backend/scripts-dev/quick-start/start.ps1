[CmdletBinding()]
param(
    [ValidateSet('All', 'Backend', 'Frontend')]
    [string]$Target = 'All',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'fronted'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$needsBackend = $Target -in @('All', 'Backend')
$needsFrontend = $Target -in @('All', 'Frontend')

try {
    if ($needsBackend) {
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "Backend environment missing. In '$backendRoot', run: uv sync --group dev"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $backendRoot 'app\main.py') -PathType Leaf)) {
            throw 'Backend entry point app/main.py is missing.'
        }
        & $pythonPath -c 'import fastapi, uvicorn, openai, sqlalchemy, aiosqlite, pydantic, tiktoken'
        if ($LASTEXITCODE -ne 0) {
            throw "Backend dependencies missing. In '$backendRoot', run: uv sync --group dev"
        }
        Write-Host '[OK] Backend environment and dependencies.' -ForegroundColor Green
    }

    if ($needsFrontend) {
        $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
        $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $nodeCommand -or -not $npmCommand) {
            throw 'Node.js / npm.cmd missing. Install Node.js >= 22.6 and reopen the terminal.'
        }
        $nodeVersion = & $nodeCommand.Source -p 'process.versions.node'
        if ($LASTEXITCODE -ne 0 -or [version]$nodeVersion -lt [version]'22.6.0') {
            throw 'Node.js >= 22.6 is required.'
        }
        if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules\.bin\vite.cmd') -PathType Leaf)) {
            throw "Frontend dependencies missing. In '$frontendRoot', run: npm ci"
        }
        Write-Host "[OK] Frontend dependencies, Node.js $nodeVersion." -ForegroundColor Green
    }

    $requiredPorts = @()
    if ($needsBackend) { $requiredPorts += 8000 }
    if ($needsFrontend) { $requiredPorts += 5173 }
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    foreach ($port in $requiredPorts) {
        if (@($listeners | Where-Object { $_.Port -eq $port }).Count -gt 0) {
            throw "Port $port is already listening. Stop the existing service before starting another instance."
        }
    }
    Write-Host "[OK] Required ports available: $($requiredPorts -join ', ')." -ForegroundColor Green

    if ($CheckOnly) {
        Write-Host '[OK] Startup checks passed. No services started.'
        exit 0
    }

    if ($Target -eq 'All') {
        # These are interactive service consoles, intentionally visible for logs and Ctrl+C.
        $shellPath = Join-Path $PSHOME 'powershell.exe'
        if (-not (Test-Path -LiteralPath $shellPath)) {
            $shellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
        }
        foreach ($service in @('Backend', 'Frontend')) {
            Start-Process -FilePath $shellPath -WorkingDirectory $projectRoot -WindowStyle Normal -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit',
                '-File', ('"{0}"' -f $PSCommandPath), '-Target', $service
            ) | Out-Null
        }
        Write-Host 'Backend:  http://127.0.0.1:8000/docs'
        Write-Host 'Frontend: http://127.0.0.1:5173'
        Write-Host 'Service windows opened. Wait for their ready messages; use Ctrl+C in each to stop.'
        exit 0
    }

    if ($Target -eq 'Backend') {
        $Host.UI.RawUI.WindowTitle = 'Agent Harness Backend'
        Set-Location -LiteralPath $backendRoot
        & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    } else {
        $Host.UI.RawUI.WindowTitle = 'Agent Harness Frontend'
        Set-Location -LiteralPath $frontendRoot
        & $npmCommand.Source run dev -- --host 127.0.0.1 --port 5173 --strictPort
    }
    exit $LASTEXITCODE
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
