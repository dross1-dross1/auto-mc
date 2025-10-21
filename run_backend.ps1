$ErrorActionPreference = 'Stop'

# Start Python backend using venv if present
Set-Location -LiteralPath $PSScriptRoot

# Backend reads config strictly from config.json; no .env is used

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -m backend
    exit $LASTEXITCODE
}

# Fallback to system Python
& python -m backend
exit $LASTEXITCODE


