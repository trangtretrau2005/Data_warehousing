param(
    [ValidateSet('CreateAndProcess','ProcessExisting','AlterAndProcess')][string]$Mode = 'CreateAndProcess',
    [string]$Project = 'ssas/CoffeeCubeTrang',
    [string]$Output = 'results/native_build_20261120/ssas/integrated_ssis_source'
)
# Authorized native execution. Every write is guarded to one new Trang target.
$ErrorActionPreference = 'Stop'
$serverName = 'localhost\TRANGTRETRAU'
$databaseName = 'CoffeeCube_Trang_20261120'
$clientRoot = 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
$script:identityAssembly = [Reflection.Assembly]::LoadFrom((Join-Path $clientRoot 'PrivateAssemblies\Microsoft.Identity.Client.dll'))
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender,$eventArgs)
    if($eventArgs.Name.StartsWith('Microsoft.Identity.Client,')){return $script:identityAssembly}
    $name=(New-Object Reflection.AssemblyName($eventArgs.Name)).Name+'.dll'
    foreach($dir in @($clientRoot,(Join-Path $clientRoot 'PrivateAssemblies'),(Join-Path $clientRoot 'PublicAssemblies'))){
        $candidate=Join-Path $dir $name
        if(Test-Path -LiteralPath $candidate){return [Reflection.Assembly]::LoadFrom($candidate)}
    }
    return $null
})
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.Core.dll')
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.dll')
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$attemptId=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'_'+[Guid]::NewGuid().ToString('N').Substring(0,8)
New-Item -ItemType Directory -Force -Path (Join-Path $Output 'attempts') | Out-Null
$createPath=Join-Path $Project 'CreateCoffeeCubeTrang.xmla'
$processPath=Join-Path $Project 'ProcessFull.xmla'
$createText=[IO.File]::ReadAllText((Join-Path (Get-Location) $createPath))
$processText=[IO.File]::ReadAllText((Join-Path (Get-Location) $processPath))
[xml]$create=$createText
[xml]$process=$processText
$ns=New-Object Xml.XmlNamespaceManager($create.NameTable)
$ns.AddNamespace('a','http://schemas.microsoft.com/analysisservices/2003/engine')
$defined=$create.SelectNodes('/a:Create/a:ObjectDefinition/a:Database',$ns)
if($defined.Count -ne 1 -or $defined[0].ID -ne $databaseName){throw 'Create target guard failed.'}
if($create.SelectNodes('//a:Process|//a:Delete|//a:Alter|//a:Role|//a:DatabasePermission',$ns).Count -ne 0){throw 'Unexpected server mutation inside Create payload.'}
$connectionStrings=@($create.SelectNodes('//a:ConnectionString',$ns)|ForEach-Object {$_.InnerText})
if($connectionStrings.Count -ne 1 -or $connectionStrings[0] -notmatch 'Initial Catalog=CoffeeDW_Trang_SSIS_TN03_20261120(?:;|$)'){throw 'Relational source guard failed.'}
$pn=New-Object Xml.XmlNamespaceManager($process.NameTable)
$pn.AddNamespace('a','http://schemas.microsoft.com/analysisservices/2003/engine')
if($process.SelectSingleNode('/a:Process/a:Object/a:DatabaseID',$pn).InnerText -ne $databaseName -or $process.SelectSingleNode('/a:Process/a:Type',$pn).InnerText -ne 'ProcessFull'){throw 'Process target guard failed.'}
$server=New-Object Microsoft.AnalysisServices.Server
$report=[ordered]@{started_utc=[DateTime]::UtcNow.ToString('o');server=$serverName;database=$databaseName;mode=$Mode;status='running';create_sha256=(Get-FileHash $createPath -Algorithm SHA256).Hash.ToLower();process_sha256=(Get-FileHash $processPath -Algorithm SHA256).Hash.ToLower();steps=@()}
function Save-Report {
    param($Name='deploy_process.json')
    $json=$script:report|ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $script:Output $Name)),$json,(New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText((Join-Path (Get-Location) (Join-Path $script:Output ('attempts/deploy_process_'+$script:attemptId+'.json'))),$json,(New-Object Text.UTF8Encoding($false)))
}
function Invoke-GuardedXmla {
    param([string]$Name,[string]$Text)
    $step=[ordered]@{name=$Name;started_utc=[DateTime]::UtcNow.ToString('o');messages=@();status='running'}
    try {
        # AMO wraps command fragments in Execute/SOAP; a file-level XML
        # declaration cannot be nested inside that command envelope.
        $fragment=[regex]::Replace($Text,'^\s*<\?xml[^?]*\?>\s*','')
        $responses=$script:server.Execute($fragment)
        foreach($response in $responses){
            foreach($message in $response.Messages){
                $m=[ordered]@{type=$message.GetType().FullName;description=$message.Description}
                foreach($property in @('ErrorCode','Source','HelpFile','Severity','Location')){
                    if($message.PSObject.Properties[$property]){$m[$property]=[string]$message.$property}
                }
                $step.messages+= $m
            }
        }
        if(@($step.messages|Where-Object {$_.type -like '*XmlaError'}).Count -gt 0){throw "XMLA $Name returned errors; see exact messages in report."}
        $step.status='succeeded'
    }catch{
        $step.status='failed'
        $step.exception=$_.Exception.ToString()
        throw
    }finally{
        $step.finished_utc=[DateTime]::UtcNow.ToString('o')
        $script:report.steps+= $step
        Save-Report
    }
}
try {
    $server.Connect("Data Source=$serverName;Connect Timeout=15")
    $report.server_version=$server.Version
    $report.server_mode=[string]$server.ServerMode
    $report.databases_before=@($server.Databases|ForEach-Object{[ordered]@{id=$_.ID;state=[string]$_.State}})
    $existing=$server.Databases.FindByName($databaseName)
    if($Mode -eq 'CreateAndProcess'){
        if($null -ne $existing){throw 'Target already exists. Refusing Create, overwrite or delete. Use ProcessExisting only for this owned target.'}
        Invoke-GuardedXmla 'Create' $createText
        $server.Disconnect()
        $server.Connect("Data Source=$serverName;Connect Timeout=15")
        $created=$server.Databases.FindByName($databaseName)
        if($null -eq $created){throw 'Create returned without target metadata.'}
        $receipt=[ordered]@{database=$databaseName;server=$serverName;created_utc=[DateTime]::UtcNow.ToString('o');source_database='CoffeeDW_Trang_SSIS_TN03_20261120';create_sha256=$report.create_sha256}
        $receipt|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Output 'owned_target_receipt.json') -Encoding UTF8
    }else{
        $receiptPath=Join-Path $Output 'owned_target_receipt.json'
        if(-not(Test-Path -LiteralPath $receiptPath)){
            # Recover only our own immediately preceding successful Create when
            # AMO cached child metadata prevented the first receipt read-back.
            $previousPath=Join-Path $Output 'deploy_process.json'
            if(-not(Test-Path -LiteralPath $previousPath)){throw 'Cannot resume an unowned target without creation receipt.'}
            $previous=Get-Content -LiteralPath $previousPath -Raw -Encoding UTF8|ConvertFrom-Json
            $successfulCreate=@($previous.steps|Where-Object {$_.name -eq 'Create' -and $_.status -eq 'succeeded'})
            $beforeTarget=@($previous.databases_before|Where-Object {$_.id -eq $databaseName})
            if($previous.database -ne $databaseName -or $previous.server -ne $serverName -or $previous.create_sha256 -ne $report.create_sha256 -or $successfulCreate.Count -ne 1 -or $beforeTarget.Count -ne 0 -or $null -eq $existing){throw 'No successful owned Create can be recovered.'}
            $receipt=[ordered]@{database=$databaseName;server=$serverName;created_utc=$previous.started_utc;source_database='CoffeeDW_Trang_SSIS_TN03_20261120';create_sha256=$previous.create_sha256;recovered_after_client_cache_readback=$true}
            $receipt|ConvertTo-Json|Set-Content -LiteralPath $receiptPath -Encoding UTF8
        }
        $receipt=Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8|ConvertFrom-Json
        if($receipt.database -ne $databaseName -or $receipt.server -ne $serverName -or $receipt.source_database -ne 'CoffeeDW_Trang_SSIS_TN03_20261120' -or $null -eq $existing){throw 'Resume ownership/target/source guard failed.'}
        $source=$existing.DataSources.FindByName('CoffeeDW')
        if($null -eq $source -or $source.ConnectionString -notmatch 'Initial Catalog=CoffeeDW_Trang_SSIS_TN03_20261120(?:;|$)'){throw 'Existing owned target has an unexpected data source.'}
        if($Mode -eq 'AlterAndProcess'){
            $definition=$defined[0].OuterXml
            $alterText='<Alter xmlns="http://schemas.microsoft.com/analysisservices/2003/engine" AllowCreate="false" ObjectExpansion="ExpandFull"><Object><DatabaseID>'+$databaseName+'</DatabaseID></Object><ObjectDefinition>'+$definition+'</ObjectDefinition></Alter>'
            Invoke-GuardedXmla 'AlterOwnedTarget' $alterText
            $server.Disconnect()
            $server.Connect("Data Source=$serverName;Connect Timeout=15")
        }
    }
    Invoke-GuardedXmla 'ProcessFull' $processText
    $server.Disconnect()
    $server.Connect("Data Source=$serverName;Connect Timeout=15")
    $target=$server.Databases.FindByName($databaseName)
    $target.Refresh()
    $report.target_state_after=[string]$target.State
    $report.last_processed_utc=$target.LastProcessed.ToUniversalTime().ToString('o')
    $report.databases_after=@($server.Databases|ForEach-Object{[ordered]@{id=$_.ID;state=[string]$_.State}})
    if($report.target_state_after -ne 'Processed'){throw 'ProcessFull did not leave target in Processed state.'}
    $report.status='passed'
}catch{
    $report.status='failed'
    $report.exception=$_.Exception.ToString()
    throw
}finally{
    $report.finished_utc=[DateTime]::UtcNow.ToString('o')
    if($server.Connected){$server.Disconnect()}
    Save-Report
}
$report|ConvertTo-Json -Depth 12
