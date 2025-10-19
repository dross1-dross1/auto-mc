$ErrorActionPreference = 'Stop'

# Run Gradle wrapper to build the Fabric mod
Set-Location -LiteralPath $PSScriptRoot
$fabricModDir = Join-Path $PSScriptRoot 'fabric-mod'
$gradlew = Join-Path $fabricModDir 'gradlew.bat'
if (!(Test-Path -LiteralPath $gradlew)) {
    Write-Error 'gradlew.bat not found in fabric-mod. Open README for wrapper recovery instructions.'
    exit 1
}

& $gradlew --no-daemon clean build
exit $LASTEXITCODE


