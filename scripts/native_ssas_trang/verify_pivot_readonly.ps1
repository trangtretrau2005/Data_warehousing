param([string]$Output = 'results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance')
# Read-only server capability proof: execute the exact Browser-blocked axis
# swap with ADOMD CellSet and verify its six cells against SQL and the transpose.
$ErrorActionPreference = 'Stop'
$serverName='localhost\TRANGTRETRAU'
$databaseName='CoffeeCube_Trang_20261120'
$clientRoot='C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
$script:identityAssembly=[Reflection.Assembly]::LoadFrom((Join-Path $clientRoot 'PrivateAssemblies\Microsoft.Identity.Client.dll'))
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender,$eventArgs)
    if($eventArgs.Name.StartsWith('Microsoft.Identity.Client,')){return $script:identityAssembly}
    $name=(New-Object Reflection.AssemblyName($eventArgs.Name)).Name+'.dll'
    foreach($dir in @($clientRoot,(Join-Path $clientRoot 'PrivateAssemblies'),(Join-Path $clientRoot 'PublicAssemblies'))){
        $path=Join-Path $dir $name
        if(Test-Path -LiteralPath $path){return [Reflection.Assembly]::LoadFrom($path)}
    }
    return $null
})
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.AdomdClient.dll')
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$original=@'
SELECT
  {[Measures].[Sales],[Measures].[Budget Sales],[Measures].[Profit]} ON COLUMNS,
  {[Dim Location].[Market].&[Central],[Dim Location].[Market].&[East]} ON ROWS
FROM [Coffee Performance]
WHERE ([Dim Date].[Date Key].&[20120101],[Dim Product].[Product Type].&[Coffee]);
'@
$swapped=@'
SELECT
  {[Dim Location].[Market].&[Central],[Dim Location].[Market].&[East]} ON COLUMNS,
  {[Measures].[Sales],[Measures].[Budget Sales],[Measures].[Profit]} ON ROWS
FROM [Coffee Performance]
WHERE ([Dim Date].[Date Key].&[20120101],[Dim Product].[Product Type].&[Coffee]);
'@
[IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $Output 'original_axes.mdx')),$original,(New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $Output 'swapped_axes.mdx')),$swapped,(New-Object Text.UTF8Encoding($false)))
$connection=New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=$serverName;Initial Catalog=$databaseName;Integrated Security=SSPI")
function Read-Matrix {
    param([string]$Query)
    if($Query.TrimStart() -notmatch '^SELECT\b' -or $Query -match '(?i)\b(CREATE|ALTER|DROP|UPDATE|INSERT|DELETE|CALL)\b'){throw 'Only fixed read-only SELECT MDX is allowed.'}
    $command=$script:connection.CreateCommand()
    $command.CommandText=$Query
    try {
        $cellset=$command.ExecuteCellSet()
        if($cellset.Axes.Count -ne 2){throw 'Expected a two-axis CellSet.'}
        $columns=@($cellset.Axes[0].Positions|ForEach-Object { @($_.Members|ForEach-Object {$_.Caption}) -join ' | ' })
        $rows=@($cellset.Axes[1].Positions|ForEach-Object { @($_.Members|ForEach-Object {$_.Caption}) -join ' | ' })
        $matrix=@()
        for($row=0;$row -lt $rows.Count;$row++){
            $values=@()
            for($col=0;$col -lt $columns.Count;$col++){
                $cell=$cellset.Cells.get_Item([int[]]@($col,$row))
                $values+= $cell.Value
            }
            $matrix+= ,$values
        }
        return [pscustomobject]@{columns=$columns;rows=$rows;matrix=$matrix;query=$Query}
    } finally {$command.Dispose()}
}
$report=[ordered]@{status='running';started_utc=[DateTime]::UtcNow.ToString('o');server=$serverName;database=$databaseName;execution='ADOMD ExecuteCellSet SELECT only';writes_executed=$false;deploy_or_process_executed=$false}
try {
    $connection.Open()
    $report.server_version=$connection.ServerVersion
    $report.source_database='CoffeeDW_Trang_SSIS_TN03_20261120'
    $baseline=Read-Matrix $original
    $pivot=Read-Matrix $swapped
    $report.original=$baseline
    $report.swapped=$pivot
    if($baseline.rows.Count -ne 2 -or $baseline.columns.Count -ne 3 -or $pivot.rows.Count -ne 3 -or $pivot.columns.Count -ne 2){throw 'Unexpected matrix shapes.'}
    $sql='SELECT Market,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit FROM mart.vw_Detail WHERE DateKey=20120101 AND ProductType=N''Coffee'' AND Market IN (N''Central'',N''East'') GROUP BY Market ORDER BY Market;'
    [IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $Output 'expected.sql')),$sql,(New-Object Text.UTF8Encoding($false)))
    $sqlConnection=New-Object System.Data.SqlClient.SqlConnection('Data Source=.;Initial Catalog=CoffeeDW_Trang_SSIS_TN03_20261120;Integrated Security=SSPI;Encrypt=True;TrustServerCertificate=True;Connect Timeout=15')
    try {
        $sqlConnection.Open()
        $sqlCommand=$sqlConnection.CreateCommand();$sqlCommand.CommandText=$sql
        $reader=$sqlCommand.ExecuteReader()
        $expected=@()
        try {while($reader.Read()){$expected+= [pscustomobject]@{Market=$reader.GetString(0);Sales=[decimal]$reader.GetValue(1);BudgetSales=[decimal]$reader.GetValue(2);Profit=[decimal]$reader.GetValue(3)}}} finally {$reader.Close();$sqlCommand.Dispose()}
    } finally {$sqlConnection.Close()}
    $expected|Export-Csv -LiteralPath (Join-Path $Output 'sql_expected.csv') -NoTypeInformation -Encoding UTF8
    if($expected.Count -ne 2){throw 'Expected SQL must contain exactly Central and East.'}
    $names=@('Sales','BudgetSales','Profit')
    $checks=@()
    for($r=0;$r -lt 2;$r++){
        if($baseline.rows[$r] -ne $expected[$r].Market -or $pivot.columns[$r] -ne $expected[$r].Market){throw 'Market order/identity mismatch.'}
        for($c=0;$c -lt 3;$c++){
            $expectedValue=[decimal]$expected[$r].($names[$c])
            $a=[decimal]$baseline.matrix[$r][$c]
            $b=[decimal]$pivot.matrix[$c][$r]
            $equal=($a -eq $b -and $a -eq $expectedValue)
            $checks+= [pscustomobject]@{Market=$expected[$r].Market;Measure=$names[$c];SQL=$expectedValue;Original=$a;Swapped=$b;Passed=$equal}
            if(-not $equal){throw "Cell mismatch for $($expected[$r].Market) / $($names[$c])."}
        }
    }
    $checks|Export-Csv -LiteralPath (Join-Path $Output 'cell_comparison.csv') -NoTypeInformation -Encoding UTF8
    $report.sql_expected=$expected
    $report.cell_checks=$checks
    $report.cells_compared=6
    $report.native_swapped_axes_executed=$true
    $report.exact_transpose=$true
    $report.grand_total_sales=([decimal]$expected[0].Sales+[decimal]$expected[1].Sales)
    $report.status='passed'
    $report.limit='This proves native ADOMD/SSAS execution of the Browser-blocked axis swap; it does not claim Browser designer pivot UI passed.'
} catch {
    $report.status='failed';$report.error=$_.Exception.ToString();throw
} finally {
    $connection.Close()
    $report.finished_utc=[DateTime]::UtcNow.ToString('o')
    $json=$report|ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $Output 'verification.json')),$json,(New-Object Text.UTF8Encoding($false)))
}
$report|ConvertTo-Json -Depth 10
