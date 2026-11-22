param([string]$Database='CoffeeDW_Trang_SSIS_TN03_20261120',[string]$Server='.',[string]$Evidence=(Join-Path $PSScriptRoot '../../results/native_build_20261120/ssis/scd'))
$ErrorActionPreference='Stop'
if($Database -notmatch '^CoffeeDW_Trang_[A-Za-z0-9_]+$') { throw 'Isolated CoffeeDW_Trang database required' }
if($Server -notmatch '^[.A-Za-z0-9_\\-]+$') { throw 'Local/named Windows-auth instance only' }
$run=[guid]::NewGuid().ToString(); $folder=Join-Path $Evidence $run
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$pkg=Join-Path $PSScriptRoot 'SCD_TN04_Trang.dtsx'
$snapshot=Join-Path $folder 'SCD_TN04_Trang.dtsx'; Copy-Item -LiteralPath $pkg -Destination $snapshot
$manifest=[ordered]@{RunID=$run;Database=$Database;Server=$Server;StartedUTC=[DateTime]::UtcNow.ToString('o');PackageSHA256=(Get-FileHash -LiteralPath $snapshot -Algorithm SHA256).Hash.ToLowerInvariant();Status='STARTED';Scope='Synthetic temp-table SCD; no serving dimensions'}
$mp=Join-Path $folder 'manifest.json';$manifest|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $mp -Encoding UTF8
$args=@('/FILE',$snapshot,'/REPORTING','V','/SET',('\Package.Variables[User::ServerName].Properties[Value];'+$Server),'/SET',('\Package.Variables[User::DatabaseName].Properties[Value];'+$Database),'/SET',('\Package.Variables[User::RunID].Properties[Value];'+$run))
$exe='C:/Program Files/Microsoft SQL Server/160/DTS/Binn/DTExec.exe'
& $exe @args 2>&1 | Tee-Object -Variable output | Out-File -LiteralPath (Join-Path $folder 'dtexec.log') -Encoding UTF8
$manifest.ExitCode=$LASTEXITCODE;$manifest.FinishedUTC=[DateTime]::UtcNow.ToString('o')
$cn=New-Object Data.SqlClient.SqlConnection("Server=$Server;Database=$Database;Integrated Security=True;TrustServerCertificate=True;")
try{$cn.Open();$cmd=$cn.CreateCommand();$cmd.CommandText='SELECT ResultJson FROM audit.SCDNativeEvidence WHERE RunID=@id';[void]$cmd.Parameters.Add('@id',[Data.SqlDbType]::UniqueIdentifier);$cmd.Parameters['@id'].Value=[guid]$run;$json=$cmd.ExecuteScalar();if($null -ne $json){$manifest.Result=($json|ConvertFrom-Json);$manifest.Status='SUCCEEDED'}else{$manifest.Status='FAILED'}}finally{$cn.Dispose()}
$manifest|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $mp -Encoding UTF8
$output|Write-Output;Write-Output "RunID=$run; Evidence=$folder"
if($LASTEXITCODE -ne 0 -or $manifest.Status -ne 'SUCCEEDED'){throw 'SCD native execution failed; inspect evidence log'}
