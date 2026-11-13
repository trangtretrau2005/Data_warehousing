param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $Python) {
    $localPython = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'
    if (Test-Path -LiteralPath $localPython) { $Python = $localPython }
    else { $Python = 'python' }
}
& $Python -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Cannot run Python 3.11+. Pass -Python with a working python.exe path.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& '.venv/Scripts/python.exe' -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed' }
Write-Output 'Ready. Run .venv/Scripts/python -m coffee_dw.cli demo'
