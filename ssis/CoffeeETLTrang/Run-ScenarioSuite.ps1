param([string]$Database='CoffeeDW_Trang_SSIS_TN03_20261120',[string]$Server='.')
$ErrorActionPreference='Stop'
if($Database -notmatch '^CoffeeDW_Trang_[A-Za-z0-9_]+$') { throw 'Isolated database required' }
if($Server -notmatch '^[.A-Za-z0-9_\\-]+$') { throw 'Use a local/named Windows-auth instance only' }
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python=Join-Path $root '.venv/Scripts/python.exe'
$fixture=Join-Path $root 'results/native_build_20261120/ssis/fixtures'
$evidence=Join-Path $root ('results/native_build_20261120/ssis/scenario_suite_'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
function Snapshot {
 $cn=New-Object Data.SqlClient.SqlConnection("Server=$Server;Database=$Database;Integrated Security=True;TrustServerCertificate=True;")
 try {
  $cn.Open(); $command=$cn.CreateCommand()
  $command.CommandText='SELECT COUNT_BIG(*) Rows,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit FROM dw.FactSalesPerformance;'
  $reader=$command.ExecuteReader(); [void]$reader.Read()
  return [ordered]@{Rows=[long]$reader['Rows'];Sales=if($reader.IsDBNull(1)){0}else{[decimal]$reader['Sales']};BudgetSales=if($reader.IsDBNull(2)){0}else{[decimal]$reader['BudgetSales']};Profit=if($reader.IsDBNull(3)){0}else{[decimal]$reader['Profit']}}
 } finally { $cn.Dispose() }
}
$initial=Snapshot
if($initial.Rows -ne 0) { throw 'The 23-to-24-month proof requires an empty experiment fact. Do not delete existing data; use a new initialized DB.' }
$cases=@(
 @{Name='01_first23';File=(Join-Path $fixture 'first_23_months.csv');Rows=4071;Sales=784231},
 @{Name='02_add_december';File=(Join-Path $fixture 'month_201312.csv');Rows=4248;Sales=819811},
 @{Name='03_replay_december';File=(Join-Path $fixture 'month_201312.csv');Rows=4248;Sales=819811},
 @{Name='04_correct_sales';File=(Join-Path $fixture 'correction_sales_plus_10.csv');Rows=4248;Sales=819821},
 @{Name='05_restore_raw';File=(Join-Path $root 'data/raw/Coffee.csv');Rows=4248;Sales=819811},
 @{Name='06_full_one_bad_numeric';File=(Join-Path $fixture 'invalid_full_one_numeric.csv');Rows=4248;Sales=819811},
 @{Name='07_invalid8';File=(Join-Path $fixture 'invalid_8_rows.csv');Rows=4248;Sales=819811},
 @{Name='08_final_original';File=(Join-Path $root 'data/raw/Coffee.csv');Rows=4248;Sales=819811}
)
$report=[ordered]@{Database=$Database;StartedUTC=[DateTime]::UtcNow.ToString('o');Status='STARTED';Initial=$initial;Cases=@();Scope='Actual native DTExec only. A licensing error is BLOCKED, never silently replaced by Python ETL.'}
try {
 foreach($case in $cases) {
  $folder=Join-Path $evidence $case.Name
  New-Item -ItemType Directory -Path $folder -Force | Out-Null
  & (Join-Path $PSScriptRoot 'Run-CoffeeETL.ps1') -SourceFile $case.File -Server $Server -Database $Database -Evidence $folder *> (Join-Path $folder 'launcher.log')
  $manifestPath=Get-ChildItem -LiteralPath $folder -Recurse -Filter manifest.json | Select-Object -First 1 -ExpandProperty FullName
  $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  & $python (Join-Path $PSScriptRoot 'Verify-NativeBatch.py') --source $case.File --batch-id $manifest.BatchID --database $Database --server $Server --output (Join-Path $folder 'verification.json')
  if($LASTEXITCODE -ne 0) { throw "Batch verification failed: $($case.Name)" }
  $snapshot=Snapshot
  if($snapshot.Rows -ne $case.Rows -or $snapshot.Sales -ne $case.Sales) { throw "Warehouse invariant failed: $($case.Name)" }
  $report.Cases+=@{Name=$case.Name;BatchID=$manifest.BatchID;Status='PASS';Snapshot=$snapshot;ExpectedRows=$case.Rows;ExpectedSales=$case.Sales}
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'suite.json') -Encoding UTF8
 }
 $report.Status='PASS'
} catch {
 $report.Status='BLOCKED_OR_FAILED';$report.Error=$_.Exception.Message
 throw
} finally {
 $report.FinishedUTC=[DateTime]::UtcNow.ToString('o');$report.Final=Snapshot
 $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'suite.json') -Encoding UTF8
 Write-Output "Native scenario evidence: $evidence"
}
