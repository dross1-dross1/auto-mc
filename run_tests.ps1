$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot

# 1) Java tests (Fabric mod)
$fabricModDir = Join-Path $PSScriptRoot 'fabric-mod'
$gradlew = Join-Path $fabricModDir 'gradlew.bat'
if (Test-Path -LiteralPath $gradlew) {
    & $gradlew --no-daemon test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Warning 'gradlew.bat not found; skipping Java tests. See README for wrapper recovery.'
}

# 2) Python tests (backend/test)
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) {
    & $venvPython -m unittest discover -s backend/test -p test_*.py -q
    exit $LASTEXITCODE
}

# Fallback to system Python
& python -m unittest discover -s backend/test -p test_*.py -q
exit $LASTEXITCODE


