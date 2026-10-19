[CmdletBinding()]
param(
    [ValidateSet('All', 'Backend', 'Frontend')]
    [string]$Target = 'All',
    [switch]$CheckOnly,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'fronted'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$needsBackend = $Target -in @('All', 'Backend')
$needsFrontend = $Target -in @('All', 'Frontend')

function Get-ProjectListener {
    param([int]$Port)
    $projectPattern = [regex]::Escape($projectRoot.Replace('/', '\')) + '(?=[\\/"\s]|$)'
    foreach ($listener in @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        $listenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction Stop
        if (-not $listenerProcess) { throw "Cannot inspect listener on port $Port." }
        $expected = if ($Port -eq 8000) {
            $listenerProcess.Name -eq 'python.exe' -and $listenerProcess.CommandLine -match 'uvicorn\s+app\.main:app'
        } else {
            $listenerProcess.Name -eq 'node.exe' -and $listenerProcess.CommandLine -match 'vite'
        }
        if (-not $expected) { throw "Port $Port belongs to another service. No processes stopped." }
        $ancestor = $listenerProcess
        $owned = $false
        for ($depth = 0; $depth -lt 6 -and $ancestor; $depth++) {
            if ($ancestor.CommandLine.Replace('/', '\') -match $projectPattern) {
                $owned = $true
                break
            }
            if (-not $ancestor.ParentProcessId) { break }
            $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$($ancestor.ParentProcessId)" -ErrorAction Stop
        }
        if (-not $owned) {
            throw "Cannot verify project ownership of port $Port. Stop that service manually. No processes stopped."
        }
        [pscustomobject]@{ Port = $Port; ProcessId = $listenerProcess.ProcessId; Created = $listenerProcess.CreationDate }
    }
}

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
    $restartListeners = @()
    foreach ($port in $requiredPorts) {
        if (@($listeners | Where-Object { $_.Port -eq $port }).Count -gt 0) {
            if (-not $Restart) {
                throw "Port $port is already listening. Stop the existing service or use restart.bat."
            }
            $verified = @(Get-ProjectListener -Port $port)
            if (-not $verified.Count) { throw "Port $port changed while checking. Retry." }
            $restartListeners += $verified
        }
    }
    Write-Host "[OK] Required ports checked: $($requiredPorts -join ', ')." -ForegroundColor Green

    if ($CheckOnly) {
        if ($Restart) {
            foreach ($item in $restartListeners) { Write-Host "[CHECK] Would stop project listener PID $($item.ProcessId) on port $($item.Port)." }
        }
        Write-Host '[OK] Checks passed. No services stopped or started.'
        exit 0
    }

    if ($Restart) {
        # Validate every target before stopping any of them, including PID reuse.
        foreach ($item in $restartListeners) {
            $current = @(Get-ProjectListener -Port $item.Port)
            if (-not ($current | Where-Object { $_.ProcessId -eq $item.ProcessId -and $_.Created -eq $item.Created })) {
                throw 'Listener changed after preflight. Retry. No processes stopped.'
            }
        }
        Write-Host '[RESTART] Running and queued tasks will be interrupted.' -ForegroundColor Yellow
        foreach ($item in @($restartListeners | Sort-Object ProcessId -Unique)) {
            Stop-Process -Id $item.ProcessId -ErrorAction Stop
            Write-Host "[STOP] Project listener PID $($item.ProcessId) on port $($item.Port)."
        }
        $stopDeadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            $remaining = @([System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -in $requiredPorts })
            if (-not $remaining.Count) { break }
            if ([DateTime]::UtcNow -ge $stopDeadline) { throw 'Ports did not become available after stopping. Check existing service windows.' }
            Start-Sleep -Milliseconds 100
        } while ($true)
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
