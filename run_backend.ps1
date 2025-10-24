$ErrorActionPreference = 'Stop'

# Always use system Python; no venv support
Set-Location -LiteralPath $PSScriptRoot

# Guard: require settings/config.json so failures don't flash and close
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'settings/config.json'))) {
    Write-Host 'settings/config.json not found. Create it using the example in README.' -ForegroundColor Yellow
    Read-Host -Prompt 'Press Enter to exit'
    exit 1
}

$exitCode = 1

# Proactively free the port in case another backend instance is running
try {
    $port = 8765
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pid = ($conns | Select-Object -First 1 -ExpandProperty OwningProcess)
        if ($pid) {
            Write-Host ("Port {0} in use by PID {1}. Stopping..." -f $port, $pid) -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 200
        }
    }
} catch {
    # Non-fatal; continue to attempt start
}

# Prefer "python"; fall back to Python Launcher "py -3" on Windows
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m backend
    $exitCode = $LASTEXITCODE
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m backend
    $exitCode = $LASTEXITCODE
} else {
    Write-Host 'Python was not found on PATH. Install Python 3.10+ and ensure "python" is available.' -ForegroundColor Red
    Read-Host -Prompt 'Press Enter to exit'
    exit 1
}

if ($exitCode -ne 0) {
    Write-Host ("Backend exited with code {0}. Common causes:" -f $exitCode) -ForegroundColor Yellow
    Write-Host ' - Missing Python package: install with: pip install websockets'
    Write-Host ' - Invalid or missing settings/config.json keys: see docs/config.md'
    Read-Host -Prompt 'Press Enter to exit'
}

exit $exitCode


