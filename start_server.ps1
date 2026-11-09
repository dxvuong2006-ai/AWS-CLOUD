#requires -Version 5.1
# Delegate to the shared launcher; no embedded Python pre-flight checks.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'run.bat')
if ($LASTEXITCODE -ne 0) {
    throw "LearnCloud stopped with exit code $LASTEXITCODE."
}

