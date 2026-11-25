param(
    [string]$Project = 'ssas/CoffeeCubeTrang/CoffeeCube.dwproj',
    [string]$Output = 'results/native_build_20261120/ssas/designer_configuration'
)
# Local Visual Studio user settings only. No server connection, deploy or
# processing command is issued. Run while the VS project is closed.
$ErrorActionPreference = 'Stop'
$requiredServer = 'localhost\TRANGTRETRAU'
$requiredDatabase = 'CoffeeCube_Trang_20261120'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$projectPath = [IO.Path]::GetFullPath((Join-Path $root $Project))
$expectedPath = [IO.Path]::GetFullPath((Join-Path $root 'ssas/CoffeeCubeTrang/CoffeeCube.dwproj'))
if ($projectPath -ne $expectedPath -or -not (Test-Path -LiteralPath $projectPath)) { throw 'Only the checked-in isolated Trang project is supported.' }
$beforeProjectHash = (Get-FileHash -LiteralPath $projectPath -Algorithm SHA256).Hash
$userPath = $projectPath + '.user'
$outputPath = [IO.Path]::GetFullPath((Join-Path $root $Output))
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
$backup = $null
if (Test-Path -LiteralPath $userPath) {
    $backup = Join-Path $outputPath ('CoffeeCube.dwproj.user.before_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.xml')
    Copy-Item -LiteralPath $userPath -Destination $backup
    [xml]$doc = [IO.File]::ReadAllText($userPath)
} else {
    [xml]$doc = '<AnalysisServicesUserConfiguration><Configurations><Configuration><Name>Development</Name><Options><StartObject><ObjectId></ObjectId><ObjectType>Current</ObjectType></StartObject></Options></Configuration></Configurations></AnalysisServicesUserConfiguration>'
}
if ($doc.DocumentElement.LocalName -ne 'AnalysisServicesUserConfiguration') { throw 'Unexpected local user configuration root.' }
$configuration = $doc.SelectSingleNode('/AnalysisServicesUserConfiguration/Configurations/Configuration[Name="Development"]')
if ($null -eq $configuration) { throw 'Development configuration is missing; refusing to alter other configurations.' }
$options = $configuration.SelectSingleNode('Options')
if ($null -eq $options) { $options = $doc.CreateElement('Options'); [void]$configuration.AppendChild($options) }
foreach ($setting in @(@('TargetServer',$requiredServer),@('TargetDatabase',$requiredDatabase))) {
    $element = $options.SelectSingleNode($setting[0])
    if ($null -eq $element) { $element = $doc.CreateElement($setting[0]); [void]$options.AppendChild($element) }
    $element.InnerText = $setting[1]
}
$writerSettings = New-Object Xml.XmlWriterSettings
$writerSettings.Indent = $true
$writerSettings.Encoding = New-Object Text.UTF8Encoding($false)
$writer = [Xml.XmlWriter]::Create($userPath, $writerSettings)
try { $doc.Save($writer) } finally { $writer.Close() }
[xml]$verified = [IO.File]::ReadAllText($userPath)
$actualServer = $verified.SelectSingleNode('/AnalysisServicesUserConfiguration/Configurations/Configuration[Name="Development"]/Options/TargetServer').InnerText
$actualDatabase = $verified.SelectSingleNode('/AnalysisServicesUserConfiguration/Configurations/Configuration[Name="Development"]/Options/TargetDatabase').InnerText
if ($actualServer -ne $requiredServer -or $actualDatabase -ne $requiredDatabase) { throw 'Local deployment-target read-back did not match the isolated target.' }
if ((Get-FileHash -LiteralPath $projectPath -Algorithm SHA256).Hash -ne $beforeProjectHash) { throw 'Shared project metadata unexpectedly changed.' }
$report = [ordered]@{status='configured';timestamp_utc=[DateTime]::UtcNow.ToString('o');project=$projectPath;user_file=$userPath;backup=$backup;configuration='Development';target_server=$actualServer;target_database=$actualDatabase;shared_project_unchanged=$true;server_connections_opened=0;deployment_executed=$false;processing_executed=$false;git_note='Keep *.dwproj.user ignored; rerun this script after clone.'}
$report|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $outputPath 'verification.json') -Encoding UTF8
$report|ConvertTo-Json -Depth 4
