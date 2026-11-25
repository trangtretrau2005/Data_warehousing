param(
    [ValidateSet('sqlite', 'sqlserver')][string]$Backend = 'sqlite',
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$NativeDatabase = 'CoffeeDW_Trang_20261119',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Chay scripts/setup.ps1 truoc.' }
$logs = Join-Path $projectRoot 'results/trang_completion/runtime'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$env:COFFEE_DW_BACKEND = $Backend
if ($Backend -eq 'sqlserver' -and -not $env:COFFEE_DW_SQLSERVER_CONNECTION) {
    # Local Windows authentication; no credential is embedded or written to .env.
    $env:COFFEE_DW_SQLSERVER_CONNECTION = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=$NativeDatabase;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"
}
$apps = @(
    @{Port=8501; Path='apps/dashboard/app.py'; Name='dashboard'},
    @{Port=8502; Path='apps/forecast_demo/app.py'; Name='forecast_demo'}
)
foreach ($app in $apps) {
    $listener = Get-NetTCPConnection -LocalPort $app.Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        $arguments = "-m streamlit run $($app.Path) --server.port $($app.Port) --server.address 127.0.0.1 --server.headless true"
        Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logs "$($app.Name).out.log") `
            -RedirectStandardError (Join-Path $logs "$($app.Name).err.log")
        Write-Output "Started $($app.Name): http://localhost:$($app.Port)"
    } else {
        Write-Output "Port $($app.Port) already running. Verify the source label in the app; this script does not replace an existing process."
    }
    if (-not $NoBrowser) { Start-Process "http://localhost:$($app.Port)" }
}
