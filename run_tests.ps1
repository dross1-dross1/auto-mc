$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot

# 1) Java tests (Fabric mod)
$fabricModDir = Join-Path $PSScriptRoot 'fabric-mod'
$gradlew = Join-Path $fabricModDir 'gradlew.bat'
if (Test-Path -LiteralPath $gradlew) {
    Push-Location $fabricModDir
    try {
        # Skip Java tests if JAVA_HOME or 'java' is not available
        $javaOk = $false
        if ($env:JAVA_HOME -and (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
            $javaOk = $true
        } else {
            $javaCmd = Get-Command java -ErrorAction SilentlyContinue
            if ($javaCmd) { $javaOk = $true }
        }
        if ($javaOk) {
            & $gradlew --no-daemon test jacocoTestReport
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        } else {
            Write-Warning 'Java not found (JAVA_HOME or java on PATH). Skipping Java tests.'
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Warning 'gradlew.bat not found; skipping Java tests. See README for wrapper recovery.'
}

# 2) Python tests (backend/test) - always use system Python (with coverage if available)
try {
    python -m coverage --version *> $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        python -m coverage run -m unittest discover -s backend/test -p test_*.py -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        python -m coverage xml -o coverage-backend.xml
        python -m coverage report -m
    } else {
        & python -m unittest discover -s backend/test -p test_*.py -q
    }
} catch {
    & python -m unittest discover -s backend/test -p test_*.py -q
}
exit $LASTEXITCODE


