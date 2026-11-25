param(
    [string]$Cases = 'results/native_build_20261120/ssas/integrated_ssis_source/acceptance_cases.json',
    [string]$Output = 'results/native_build_20261120/ssas/integrated_ssis_source/mdx_actual'
)
# READ ONLY: executes only the predeclared SELECT statements; no XMLA Execute,
# deploy, process, security changes or other server mutations are exposed here.
$ErrorActionPreference = 'Stop'
$clientRoot = 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
$script:identityAssembly = [Reflection.Assembly]::LoadFrom((Join-Path $clientRoot 'PrivateAssemblies\Microsoft.Identity.Client.dll'))
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender, $eventArgs)
    if ($eventArgs.Name.StartsWith('Microsoft.Identity.Client,')) { return $script:identityAssembly }
    $name = (New-Object Reflection.AssemblyName($eventArgs.Name)).Name + '.dll'
    foreach ($dir in @($clientRoot, (Join-Path $clientRoot 'PrivateAssemblies'), (Join-Path $clientRoot 'PublicAssemblies'))) {
        $candidate = Join-Path $dir $name
        if (Test-Path -LiteralPath $candidate) { return [Reflection.Assembly]::LoadFrom($candidate) }
    }
    return $null
})
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.AdomdClient.dll')
$bundle = Get-Content -LiteralPath $Cases -Raw -Encoding UTF8 | ConvertFrom-Json
if ($bundle.database -ne 'CoffeeCube_Trang_20261120') { throw 'Only the isolated Trang database is allowed.' }
if ($bundle.server -ne 'localhost\TRANGTRETRAU' -or $bundle.source_database -ne 'CoffeeDW_Trang_SSIS_TN03_20261120') { throw 'Integrated source/server acceptance guard failed.' }
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=$($bundle.server);Initial Catalog=$($bundle.database);Integrated Security=SSPI")
$results = @()
try {
    $connection.Open()
    foreach ($case in $bundle.cases) {
        if ($case.mdx.TrimStart() -notmatch '^(SELECT|WITH)\b' -or $case.mdx -notmatch '(?i)\bSELECT\b' -or $case.mdx -match '(?i)\b(CREATE|ALTER|DROP|UPDATE|DELETE|INSERT|CALL)\b') {
            throw "Non-read-only statement refused: $($case.id)"
        }
        $command = $connection.CreateCommand()
        $command.CommandText = $case.mdx
        try {
            $reader = $command.ExecuteReader()
            try {
                $columns = @(0..($reader.FieldCount - 1) | ForEach-Object { $reader.GetName($_) })
                $rows = @()
                while ($reader.Read()) {
                    $values = [ordered]@{}
                    for ($i=0; $i -lt $reader.FieldCount; $i++) {
                        $values[$columns[$i]] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) }
                    }
                    $rows += [pscustomobject]$values
                }
                $rows | Export-Csv -LiteralPath (Join-Path $Output ($case.id + '.csv')) -NoTypeInformation -Encoding UTF8
                $results += [ordered]@{id=$case.id;status='executed';row_count=$rows.Count;columns=$columns;query=$case.mdx}
            } finally { $reader.Close() }
        } catch {
            $results += [ordered]@{id=$case.id;status='failed';error=$_.Exception.Message;query=$case.mdx}
        } finally { $command.Dispose() }
    }
} finally { $connection.Close() }
$report = [ordered]@{server=$bundle.server;database=$bundle.database;timestamp_utc=[DateTime]::UtcNow.ToString('o');execution='ADOMD read-only SELECT';results=$results;writes_executed=$false}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Output 'execution.json') -Encoding UTF8
$results | ForEach-Object {[pscustomobject]$_} | Select-Object id,status,row_count,error | Format-Table -AutoSize
if (@($results | Where-Object {$_.status -eq 'failed'}).Count -gt 0) { exit 1 }
