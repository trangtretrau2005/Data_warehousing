param([string]$Output = 'results/native_build_20261120/ssas/integrated_ssis_source')
# Authorized narrow migration: existing isolated cube, existing Windows login,
# new SSIS-populated relational database. No CREATE/DROP database/cube or roles.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$serverName='localhost\TRANGTRETRAU';$cubeDatabase='CoffeeCube_Trang_20261120'
$oldDatabase='CoffeeDW_Trang_20261119';$newDatabase='CoffeeDW_Trang_SSIS_TN03_20261120'
$principal='NT Service\MSOLAP$TRANGTRETRAU'
$out=[IO.Path]::GetFullPath((Join-Path $root $Output))
New-Item -ItemType Directory -Force -Path $out | Out-Null
$attempt=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$backup=Join-Path $out ('backup_before_'+$attempt)
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$clientRoot='C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
$script:identityAssembly=[Reflection.Assembly]::LoadFrom((Join-Path $clientRoot 'PrivateAssemblies\Microsoft.Identity.Client.dll'))
[AppDomain]::CurrentDomain.add_AssemblyResolve({
 param($s,$e)
 if($e.Name.StartsWith('Microsoft.Identity.Client,')){return $script:identityAssembly}
 $name=(New-Object Reflection.AssemblyName($e.Name)).Name+'.dll'
 foreach($dir in @($clientRoot,(Join-Path $clientRoot 'PrivateAssemblies'),(Join-Path $clientRoot 'PublicAssemblies'))){$p=Join-Path $dir $name;if(Test-Path -LiteralPath $p){return [Reflection.Assembly]::LoadFrom($p)}}
 return $null
})
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.Core.dll')
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.dll')
function Save-Json($Path,$Value){[IO.File]::WriteAllText($Path,(ConvertTo-Json -InputObject $Value -Depth 14),(New-Object Text.UTF8Encoding($false)))}
function Open-Sql([string]$Database){
 if($Database -notin @($script:oldDatabase,$script:newDatabase)){throw 'Unexpected SQL catalog.'}
 $c=New-Object Data.SqlClient.SqlConnection("Data Source=.;Initial Catalog=$Database;Integrated Security=SSPI;Encrypt=True;TrustServerCertificate=True;Connect Timeout=15")
 $c.Open();return $c
}
function Sql-Rows($Connection,[string]$Query){
 $cmd=$Connection.CreateCommand();$cmd.CommandText=$Query;$cmd.CommandTimeout=60
 try{$reader=$cmd.ExecuteReader();try{$rows=@();while($reader.Read()){$r=[ordered]@{};for($i=0;$i -lt $reader.FieldCount;$i++){$r[$reader.GetName($i)]=if($reader.IsDBNull($i)){$null}else{$reader.GetValue($i)}};$rows+=[pscustomobject]$r};return ,$rows}finally{$reader.Close()}}finally{$cmd.Dispose()}
}
function Metadata($Database){
 $ds=$Database.DataSources.FindByName('CoffeeDW');if($null -eq $ds){throw 'Required DataSource CoffeeDW not found.'}
 # DbConnectionStringBuilder is dictionary-adapted in PowerShell: assigning
 # .ConnectionString creates an entry instead of calling the CLR setter.
 $b=New-Object Data.Common.DbConnectionStringBuilder;$b.set_ConnectionString($ds.ConnectionString)
 $cube=$Database.Cubes.FindByName('Coffee Performance');if($null -eq $cube){throw 'Required cube not found.'}
 $v=$Database.DataSourceViews.FindByName('CoffeeDW')
 return [ordered]@{database_id=$Database.ID;state=[string]$Database.State;source_id=$ds.ID;provider=[string]$b['Provider'];relational_server=[string]$b['Data Source'];relational_database=[string]$b['Initial Catalog'];impersonation=[string]$ds.ImpersonationInfo.ImpersonationMode;dsv_id=$v.ID;dsv_source_id=$v.DataSourceID;dsv_tables=@($v.Schema.Tables|ForEach-Object{$_.TableName});cube_id=$cube.ID;measure_count=$cube.MeasureGroups[0].Measures.Count;inventory_aggregate=[string]$cube.MeasureGroups[0].Measures.FindByName('Inventory').AggregateFunction;dimensions=@($Database.Dimensions|ForEach-Object{[ordered]@{name=$_.Name;key_duplicate=[string]$_.ErrorConfiguration.KeyDuplicate;key_not_found=[string]$_.ErrorConfiguration.KeyNotFound;null_key=[string]$_.ErrorConfiguration.NullKeyNotAllowed;null_converted=[string]$_.ErrorConfiguration.NullKeyConvertedToUnknown}});last_processed_utc=$Database.LastProcessed.ToUniversalTime().ToString('o')}
}
function Execute-Xmla([string]$Name,[string]$Xmla){
 $step=[ordered]@{name=$Name;started_utc=[DateTime]::UtcNow.ToString('o');messages=@();status='running'}
 try{$responses=$script:server.Execute($Xmla);foreach($response in $responses){foreach($message in $response.Messages){$m=[ordered]@{type=$message.GetType().FullName;description=$message.Description};if($message.PSObject.Properties['ErrorCode']){$m.error_code=$message.ErrorCode};$step.messages+=$m}};if(@($step.messages|Where-Object{$_.type -like '*XmlaError'}).Count){throw "XMLA $Name failed; inspect exact messages."};$step.status='succeeded'}catch{$step.status='failed';$step.exception=$_.Exception.ToString();throw}finally{$step.finished_utc=[DateTime]::UtcNow.ToString('o');$script:report.steps+=$step;Save-Json (Join-Path $script:out 'migration.json') $script:report}
}
$server=New-Object Microsoft.AnalysisServices.Server
$report=[ordered]@{status='running';started_utc=[DateTime]::UtcNow.ToString('o');server=$serverName;cube_database=$cubeDatabase;old_source=$oldDatabase;new_source=$newDatabase;steps=@();backup_directory=$backup}
$unchangedPaths=@('ssas/CoffeeCubeTrang/CoffeeDW.dsv','ssas/CoffeeCubeTrang/Dim Date.dim','ssas/CoffeeCubeTrang/Dim Location.dim','ssas/CoffeeCubeTrang/Dim Product.dim','ssas/CoffeeCubeTrang/Coffee Performance.cube','ssas/CoffeeCubeTrang/Coffee Performance.partitions','ssas/CoffeeCubeTrang/CoffeeCube.database')
$unchangedBefore=@{};foreach($p in $unchangedPaths){$unchangedBefore[$p]=(Get-FileHash -LiteralPath (Join-Path $root $p) -Algorithm SHA256).Hash}
$rawHash=(Get-FileHash -LiteralPath (Join-Path $root 'data/raw/Coffee.csv') -Algorithm SHA256).Hash
try{
 $server.Connect("Data Source=$serverName;Connect Timeout=15")
 $db=$server.Databases.FindByName($cubeDatabase);if($null -eq $db -or $db.ID -ne $cubeDatabase){throw 'Only the existing isolated cube may be modified.'}
 $report.server_version=$server.Version;$report.before=Metadata $db
 if($report.before.relational_database -ne $oldDatabase){throw 'Expected old source is not current; refuse a blind rewire.'}
 if($report.before.provider -ne 'MSOLEDBSQL' -or $report.before.measure_count -ne 11 -or $report.before.inventory_aggregate -ne 'LastChild'){throw 'Unexpected cube/provider contract.'}
 $my=$server.Databases.FindByName('MySalesCube');$myBefore=if($null -ne $my){$my.LastProcessed.ToUniversalTime().ToString('o')}else{$null}
 Save-Json (Join-Path $backup 'server_metadata_before.json') $report.before
 $receipt=Join-Path $root 'results/native_build_20261120/ssas/owned_target_receipt.json'
 if(Test-Path -LiteralPath $receipt){Copy-Item -LiteralPath $receipt -Destination (Join-Path $backup 'original_owned_target_receipt.json')}
 foreach($p in @('ssas/CoffeeCubeTrang/CoffeeDW.ds','ssas/CoffeeCubeTrang/CreateCoffeeCubeTrang.xmla','ssas/CoffeeCubeTrang/CoffeeCube.dwproj')){$target=Join-Path $backup ([IO.Path]::GetFileName($p));Copy-Item -LiteralPath (Join-Path $root $p) -Destination $target}

 $measures=@('Sales','BudgetSales','Profit','BudgetProfit','COGS','BudgetCOGS','Margin','BudgetMargin','Marketing','Inventory','TotalExpenses')
 $q='SELECT COUNT_BIG(*) [RowCount],'+(@($measures|ForEach-Object{"SUM([$_]) [$_]"}) -join ',')+' FROM dw.FactSalesPerformance;'
 $oldSql=Open-Sql $oldDatabase;$newSql=Open-Sql $newDatabase
 try{
  $oldTotals=(Sql-Rows $oldSql $q)[0];$newTotals=(Sql-Rows $newSql $q)[0]
  if($oldTotals.RowCount -ne 4248 -or $newTotals.RowCount -ne 4248){throw 'Both source catalogs must contain the restored 4248 facts.'}
  foreach($m in $measures){if($oldTotals.$m -ne $newTotals.$m){throw "Relational measure mismatch: $m"}}
  $report.source_totals_before=[ordered]@{original=$oldTotals;ssis=$newTotals}
  Save-Json (Join-Path $out 'source_totals_before.json') $report.source_totals_before
  $permissionQuery="SELECT p.name Principal,dp.state_desc,dp.permission_name,SCHEMA_NAME(o.schema_id) SchemaName,o.name ObjectName FROM sys.database_principals p LEFT JOIN sys.database_permissions dp ON dp.grantee_principal_id=p.principal_id LEFT JOIN sys.objects o ON dp.class=1 AND o.object_id=dp.major_id WHERE p.name=N'NT Service\MSOLAP`$TRANGTRETRAU' ORDER BY dp.class,SchemaName,ObjectName;"
  $beforePermissions=Sql-Rows $newSql $permissionQuery
  Save-Json (Join-Path $out 'permissions_before.json') $beforePermissions
  $login=(Sql-Rows $newSql "SELECT SUSER_ID(N'NT Service\MSOLAP`$TRANGTRETRAU') LoginID;")[0]
  if($null -eq $login.LoginID){throw 'The existing server login is required; this script will not create a server login.'}
  $roles=Sql-Rows $newSql "SELECT r.name RoleName FROM sys.database_role_members rm JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id JOIN sys.database_principals m ON m.principal_id=rm.member_principal_id WHERE m.name=N'NT Service\MSOLAP`$TRANGTRETRAU';"
  if($roles.Count -gt 0){throw 'Existing role membership needs review; no wide roles will be added or removed.'}
  $grant=@'
IF DB_NAME() <> N'CoffeeDW_Trang_SSIS_TN03_20261120' THROW 51000,'Unexpected SQL database',1;
IF SUSER_ID(N'NT Service\MSOLAP$TRANGTRETRAU') IS NULL THROW 51000,'Existing service login is required',1;
BEGIN TRANSACTION;
IF USER_ID(N'NT Service\MSOLAP$TRANGTRETRAU') IS NULL
 CREATE USER [NT Service\MSOLAP$TRANGTRETRAU] FOR LOGIN [NT Service\MSOLAP$TRANGTRETRAU];
GRANT CONNECT TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::dw.DimDate TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::dw.DimLocation TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::dw.DimProduct TO [NT Service\MSOLAP$TRANGTRETRAU];
GRANT SELECT ON OBJECT::dw.FactSalesPerformance TO [NT Service\MSOLAP$TRANGTRETRAU];
COMMIT;
'@
  [IO.File]::WriteAllText((Join-Path $out 'grant_narrow_source_read.sql'),$grant,(New-Object Text.UTF8Encoding($false)))
  $command=$newSql.CreateCommand();$command.CommandText=$grant;try{[void]$command.ExecuteNonQuery()}finally{$command.Dispose()}
  $afterPermissions=Sql-Rows $newSql $permissionQuery
  Save-Json (Join-Path $out 'permissions_after.json') $afterPermissions
  if($afterPermissions.Count -ne 5 -or @($afterPermissions|Where-Object{$_.permission_name -notin @('CONNECT','SELECT') -or $_.state_desc -ne 'GRANT'}).Count){throw 'Unexpected permissions after the narrow grant; refusing further server changes.'}
  $report.permissions_after=$afterPermissions
 }finally{$oldSql.Close();$newSql.Close()}

 $ds=$db.DataSources.FindByName('CoffeeDW')
 $sourceBefore=$ds.ConnectionString
 $needle='Initial Catalog='+$oldDatabase
 if(-not $sourceBefore.Contains($needle)){throw 'Exact old source catalog was not found in the current data source.'}
 $newConnection=$sourceBefore.Replace($needle,'Initial Catalog='+$newDatabase)
 $xmlDoc=New-Object Xml.XmlDocument
 $namespace='http://schemas.microsoft.com/analysisservices/2003/engine'
 $alter=$xmlDoc.CreateElement('Alter',$namespace);[void]$xmlDoc.AppendChild($alter)
 $alter.SetAttribute('AllowCreate','false');$alter.SetAttribute('ObjectExpansion','ExpandFull')
 $object=$xmlDoc.CreateElement('Object',$namespace);[void]$alter.AppendChild($object)
 foreach($pair in @(@('DatabaseID',$cubeDatabase),@('DataSourceID','CoffeeDW'))){$n=$xmlDoc.CreateElement($pair[0],$namespace);$n.InnerText=$pair[1];[void]$object.AppendChild($n)}
 $definition=$xmlDoc.CreateElement('ObjectDefinition',$namespace);[void]$alter.AppendChild($definition)
 [xml]$localSource=[IO.File]::ReadAllText((Join-Path $root 'ssas/CoffeeCubeTrang/CoffeeDW.ds'))
 $sourceNode=$xmlDoc.ImportNode($localSource.DocumentElement,$true)
 $xn=New-Object Xml.XmlNamespaceManager($xmlDoc.NameTable);$xn.AddNamespace('a',$namespace)
 $sourceNode.SelectSingleNode('a:ConnectionString',$xn).InnerText=$newConnection
 [void]$definition.AppendChild($sourceNode)
 [IO.File]::WriteAllText((Join-Path $out 'alter_datasource_only.xmla'),$xmlDoc.OuterXml,(New-Object Text.UTF8Encoding($false)))
 Execute-Xmla 'AlterDataSourceOnly' $xmlDoc.OuterXml
 $server.Disconnect();$server.Connect("Data Source=$serverName;Connect Timeout=15")
 $db=$server.Databases.FindByName($cubeDatabase);$afterSource=Metadata $db
 if($afterSource.relational_database -ne $newDatabase -or $afterSource.provider -ne $report.before.provider){throw 'Server data source read-back did not match the intended catalog/provider.'}
 $process='<Process xmlns="http://schemas.microsoft.com/analysisservices/2003/engine"><Object><DatabaseID>'+ $cubeDatabase +'</DatabaseID></Object><Type>ProcessFull</Type><WriteBackTableCreation>UseExisting</WriteBackTableCreation></Process>'
 [IO.File]::WriteAllText((Join-Path $out 'process_full_existing_cube.xmla'),$process,(New-Object Text.UTF8Encoding($false)))
 Execute-Xmla 'ProcessFullExistingCube' $process
 $server.Disconnect();$server.Connect("Data Source=$serverName;Connect Timeout=15")
 $report.after=Metadata ($server.Databases.FindByName($cubeDatabase))
 if($report.after.state -ne 'Processed' -or $report.after.relational_database -ne $newDatabase -or $report.after.inventory_aggregate -ne 'LastChild'){throw 'Processed cube read-back failed.'}
 foreach($dim in $report.after.dimensions){if($dim.key_duplicate -ne 'ReportAndStop' -or $dim.key_not_found -ne 'ReportAndStop' -or $dim.null_key -ne 'ReportAndStop' -or $dim.null_converted -ne 'ReportAndStop'){throw 'Dimension error configuration changed.'}}
 foreach($p in @('ssas/CoffeeCubeTrang/CoffeeDW.ds','ssas/CoffeeCubeTrang/CreateCoffeeCubeTrang.xmla','ssas/CoffeeCubeTrang/CoffeeCube.dwproj')){
  $path=Join-Path $root $p;$text=[IO.File]::ReadAllText($path)
  if(-not $text.Contains($needle)){throw "Expected old catalog missing in local metadata: $p"}
  [IO.File]::WriteAllText($path,$text.Replace($needle,'Initial Catalog='+$newDatabase),(New-Object Text.UTF8Encoding($false)))
 }
 foreach($p in $unchangedPaths){if((Get-FileHash -LiteralPath (Join-Path $root $p) -Algorithm SHA256).Hash -ne $unchangedBefore[$p]){throw "Unrelated metadata changed: $p"}}
 if((Get-FileHash -LiteralPath (Join-Path $root 'data/raw/Coffee.csv') -Algorithm SHA256).Hash -ne $rawHash){throw 'Raw source changed.'}
 $my=$server.Databases.FindByName('MySalesCube');$myAfter=if($null -ne $my){$my.LastProcessed.ToUniversalTime().ToString('o')}else{$null}
 if($myBefore -ne $myAfter){throw 'Existing MySalesCube process timestamp changed.'}
 $report.my_sales_cube_last_processed_before=$myBefore;$report.my_sales_cube_last_processed_after=$myAfter
 $report.unrelated_local_metadata_unchanged=$true;$report.raw_sha256=$rawHash.ToLower();$report.status='passed'
 $newReceipt=[ordered]@{database=$cubeDatabase;server=$serverName;source_database=$newDatabase;previous_source_database=$oldDatabase;integration_utc=[DateTime]::UtcNow.ToString('o');operation='Alter datasource connection only, then ProcessFull existing cube';original_creation_receipt_preserved=$receipt;backup=$backup}
 Save-Json (Join-Path $out 'owned_target_receipt.json') $newReceipt
}catch{$report.status='failed';$report.exception=$_.Exception.ToString();throw}
finally{$report.finished_utc=[DateTime]::UtcNow.ToString('o');if($server.Connected){$server.Disconnect()};Save-Json (Join-Path $out 'migration.json') $report;Save-Json (Join-Path $out ('migration_'+$attempt+'.json')) $report}
$report|ConvertTo-Json -Depth 14
