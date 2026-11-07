# Requires only the Python + pip already used in the LearnCloud project.
$ErrorActionPreference = "Stop"
$repoPython = "D:\projects\main projects\AWS-CLOUD\.venv\Scripts\python.exe"
if (Test-Path $repoPython) {
    $pythonExe = $repoPython
} else {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

$work = Join-Path $env:TEMP "learncloud-lambda-rds-probe-package"
$package = Join-Path $work "package"
$output = Join-Path $PSScriptRoot "learncloud-rds-probe.zip"
if (Test-Path $work) { Remove-Item -Path $work -Recurse -Force }
New-Item -ItemType Directory -Path $package -Force | Out-Null

Write-Host "[1/4] Downloading pure-Python PostgreSQL client into temp package folder..."
& $pythonExe -m pip install --disable-pip-version-check --no-input --target $package "pg8000>=1.31.2,<1.32"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "[2/4] Downloading official Amazon RDS Singapore CA bundle..."
Invoke-WebRequest -Uri "https://truststore.pki.rds.amazonaws.com/ap-southeast-1/ap-southeast-1-bundle.pem" -OutFile (Join-Path $package "ap-southeast-1-bundle.pem")
if (-not (Select-String -Path (Join-Path $package "ap-southeast-1-bundle.pem") -Pattern "BEGIN CERTIFICATE" -Quiet)) {
    throw "RDS CA bundle download is invalid"
}
Copy-Item (Join-Path $PSScriptRoot "lambda_function.py") (Join-Path $package "lambda_function.py")

Write-Host "[3/4] Creating Lambda deployment ZIP..."
if (Test-Path $output) { Remove-Item $output -Force }
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $output -CompressionLevel Optimal

Write-Host "[4/4] Checking ZIP root structure..."
Add-Type -AssemblyName System.IO.Compression
$zip = [System.IO.Compression.ZipFile]::OpenRead($output)
try {
    $names = @($zip.Entries | ForEach-Object { $_.FullName })
    foreach ($name in @("lambda_function.py", "ap-southeast-1-bundle.pem")) {
        if ($names -notcontains $name) { throw "ZIP missing $name" }
    }
} finally { $zip.Dispose() }
Write-Host "DONE. Upload this ZIP via Lambda > Code > Upload from > .zip file:"
Write-Host $output
