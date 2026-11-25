param([Parameter(Mandatory=$true)][string]$ProjectFolder=$PSScriptRoot)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$folder=(Resolve-Path -LiteralPath $ProjectFolder).Path
$ispac=Join-Path $folder 'CoffeeETLTrang.ispac'
$dtproj=Join-Path $folder 'CoffeeETLTrang.dtproj'
if(-not (Test-Path -LiteralPath $ispac)) { throw 'Build the native ispac before syncing the project descriptor' }
$archive=[IO.Compression.ZipFile]::OpenRead($ispac)
try {
 $entry=$archive.GetEntry('@Project.manifest')
 if($null -eq $entry) { throw 'SDK ispac has no @Project.manifest; refusing an incomplete .dtproj' }
 $stream=$entry.Open();$reader=New-Object IO.StreamReader($stream,[Text.Encoding]::UTF8,$true)
 try {$manifestText=$reader.ReadToEnd()} finally {$reader.Dispose();$stream.Dispose()}
 $manifest=[xml]$manifestText
 $ssns='www.microsoft.com/SqlServer/SSIS'
 $names=@($manifest.Project.Packages.Package | ForEach-Object { $_.GetAttribute('Name',$ssns) })
} finally { $archive.Dispose() }
if($names.Count -eq 0) { throw 'Project manifest lists no packages' }
$doc=New-Object xml
$doc.PreserveWhitespace=$false
$doc.Load($dtproj)
$root=$doc.DocumentElement
$existing=$root.SelectSingleNode('DeploymentModelSpecificContent')
if($null -ne $existing) { [void]$root.RemoveChild($existing) }
$specific=$doc.CreateElement('DeploymentModelSpecificContent')
$manifestNode=$doc.CreateElement('Manifest')
$imported=$doc.ImportNode($manifest.DocumentElement,$true)
[void]$manifestNode.AppendChild($imported);[void]$specific.AppendChild($manifestNode)
$dbAnchor=$root.SelectSingleNode('Database')
$dataSources=$root.SelectSingleNode('DataSources')
$dataViews=$root.SelectSingleNode('DataSourceViews')
if($null -ne $dataSources) { [void]$root.RemoveChild($dataSources) } else { $dataSources=$doc.CreateElement('DataSources') }
if($null -ne $dataViews) { [void]$root.RemoveChild($dataViews) } else { $dataViews=$doc.CreateElement('DataSourceViews') }
[void]$root.InsertAfter($dataSources,$dbAnchor)
[void]$root.InsertAfter($dataViews,$dataSources)
[void]$root.InsertAfter($specific,$dataViews)
$packages=$root.SelectSingleNode('Packages')
if($null -eq $packages) { $packages=$doc.CreateElement('Packages');[void]$root.AppendChild($packages) }
while($packages.HasChildNodes) { [void]$packages.RemoveChild($packages.FirstChild) }
foreach($name in $names) {
 $item=$doc.CreateElement('Package')
 $n=$doc.CreateElement('Name');$n.InnerText=$name
 $f=$doc.CreateElement('FullPath');$f.InnerText=$name
 [void]$item.AppendChild($n);[void]$item.AppendChild($f);[void]$packages.AppendChild($item)
}
$database=$root.SelectSingleNode('Database')
if($null -eq $database) { $database=$doc.CreateElement('Database');[void]$root.AppendChild($database) }
foreach($key in @('Name','FullPath')) {
 $child=$database.SelectSingleNode($key)
 if($null -eq $child) { $child=$doc.CreateElement($key);[void]$database.AppendChild($child) }
 $child.InnerText='CoffeeETLTrang.database'
}
$guid=$root.SelectSingleNode('ProjectGuid')
if($null -eq $guid) { $guid=$doc.CreateElement('ProjectGuid');$guid.InnerText='{102EF433-E134-4DB0-BAE6-E169633E2D16}';[void]$root.InsertAfter($guid,$root.SelectSingleNode('SchemaVersion')) }
$writerSettings=New-Object Xml.XmlWriterSettings
$writerSettings.Encoding=New-Object Text.UTF8Encoding($true)
$writerSettings.Indent=$true
$writerSettings.OmitXmlDeclaration=$false
$writer=[Xml.XmlWriter]::Create($dtproj,$writerSettings)
try { $doc.Save($writer) } finally { $writer.Dispose() }
# SSIS projects retain an Analysis Services designer database item even when
# this SSIS project has no cube. Use the blank designer shell generated locally
# by SSDT, preserving existing numbered backups created by Visual Studio.
$canonical=Join-Path $folder 'CoffeeETLTrang.database'
if(-not (Test-Path -LiteralPath $canonical)) {
 $template=Get-ChildItem -LiteralPath $folder -Filter 'CoffeeETLTrang *.database' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
 if($null -eq $template) { throw 'SSDT did not generate its blank .database designer file; the project manifest is complete, but reopen in Visual Studio to create it.' }
 Copy-Item -LiteralPath $template.FullName -Destination $canonical
}
Write-Output "Synced full project manifest from the built ispac; packages: $($names -join ', ')"
