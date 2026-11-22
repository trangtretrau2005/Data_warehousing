param(
 [string]$SourceFile = (Join-Path $PSScriptRoot '../../data/raw/Coffee.csv'),
 [string]$Server = '.',
 [string]$Database = 'CoffeeDW_Trang_SSIS_TN03_20261120',
 [ValidateSet(120,150,160)][int]$RuntimeVersion = 160,
 [string]$Evidence = (Join-Path $PSScriptRoot '../../results/native_build_20261120/ssis/runs')
)
$ErrorActionPreference = 'Stop'
if($Database -notmatch '^CoffeeDW_Trang_[A-Za-z0-9_]+$') { throw 'Only an isolated CoffeeDW_Trang_<run> database is allowed' }
if($Server -notmatch '^[.A-Za-z0-9_\\-]+$') { throw 'Use a local/named Windows-auth instance, without connection-string fragments' }
$SourceFile = (Resolve-Path -LiteralPath $SourceFile).Path
if($SourceFile -match '[;"]') { throw 'DTExec /SET launcher does not accept semicolon or quote in source path' }
$expected = @('Area Code','Date','Market','Market Size','Product','Product Line','Product Type','State','Type','Budget COGS','Budget Margin','Budget Profit','Budget Sales','COGS','Inventory','Margin','Marketing','Profit','Sales','Total Expenses')
$records = @(Import-Csv -LiteralPath $SourceFile -Encoding UTF8)
if($records.Count -gt 0) {
 $headers = @($records[0].PSObject.Properties.Name)
 if(($headers -join '|') -cne ($expected -join '|')) { throw 'Expected exact 20 source columns/order' }
}
$batch = [guid]::NewGuid().ToString()
$hash = (Get-FileHash -LiteralPath $SourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
$run = Join-Path $Evidence $batch
New-Item -ItemType Directory -Path $run -Force | Out-Null
$package = Join-Path $PSScriptRoot 'LoadCoffeeTrang.dtsx'
Copy-Item -LiteralPath $package -Destination (Join-Path $run 'package.dtsx')
$package = Join-Path $run 'package.dtsx'
$values = [ordered]@{
 'SourceFilePath'=$SourceFile; 'ServerName'=$Server; 'DatabaseName'=$Database; 'BatchID'=$batch;
 'SourceChecksum'=$hash; 'SourceFileName'=[IO.Path]::GetFileName($SourceFile); 'SourceCount'=$records.Count
}
$manifest = [ordered]@{
 BatchID=$batch; SourceFile=[IO.Path]::GetFileName($SourceFile); SourceSHA256=$hash;
 SourceCount=$records.Count; Database=$Database; StartedUTC=[DateTime]::UtcNow.ToString('o');
 PackageSHA256=(Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant();
 Status='STARTED'; RuntimeVersion=$RuntimeVersion; ExecutionProof='Only the exit code/log after actual execution is evidence'
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'manifest.json') -Encoding UTF8
$dtexec = "C:/Program Files/Microsoft SQL Server/$RuntimeVersion/DTS/Binn/DTExec.exe"
$arguments = @('/FILE',$package,'/REPORTING','V')
foreach($key in $values.Keys) {
 $arguments += '/SET'
 $arguments += ('\Package.Variables[User::{0}].Properties[Value];{1}' -f $key,$values[$key])
}
& $dtexec @arguments 2>&1 | Tee-Object -Variable output | Out-File -LiteralPath (Join-Path $run 'dtexec.log') -Encoding UTF8
$code=$LASTEXITCODE
$manifest.FinishedUTC=[DateTime]::UtcNow.ToString('o')
$manifest.ExitCode=$code
$manifest.SourceUnchanged=((Get-FileHash -LiteralPath $SourceFile -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hash)
$manifest.Status=if($code -eq 0 -and $manifest.SourceUnchanged) { 'SUCCEEDED' } else { 'FAILED' }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'manifest.json') -Encoding UTF8
$output | Write-Output
Write-Output "BatchID=$batch; Evidence=$run; ExitCode=$code"
if($code -ne 0 -or -not $manifest.SourceUnchanged) { throw 'Native SSIS execution failed or source changed; inspect dtexec.log' }
