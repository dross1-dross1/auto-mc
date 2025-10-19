$ErrorActionPreference = 'Stop'

# Start Python backend using venv if present
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -m backend
    exit $LASTEXITCODE
}

# Fallback to system Python
& python -m backend
exit $LASTEXITCODE


