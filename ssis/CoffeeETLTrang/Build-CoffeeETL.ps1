param([string]$SourceFile = (Join-Path $PSScriptRoot '../../data/raw/Coffee.csv'))
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$evidence = Join-Path $root 'results/native_build_20261120/ssis'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$refs = @(
  'C:/Windows/Microsoft.NET/assembly/GAC_MSIL/Microsoft.SqlServer.ManagedDTS/v4.0_16.0.0.0__89845dcd8080cc91/Microsoft.SqlServer.ManagedDTS.dll',
  'C:/Windows/Microsoft.NET/assembly/GAC_MSIL/Microsoft.SqlServer.DTSPipelineWrap/v4.0_16.0.0.0__89845dcd8080cc91/Microsoft.SqlServer.DTSPipelineWrap.dll',
  'C:/Windows/Microsoft.NET/assembly/GAC_64/Microsoft.SqlServer.DTSRuntimeWrap/v4.0_16.0.0.0__89845dcd8080cc91/Microsoft.SqlServer.DTSRuntimeWrap.dll',
  'C:/Program Files/Microsoft SQL Server/160/DTS/Tasks/Microsoft.SqlServer.SQLTask.dll'
)
foreach($ref in $refs) { if(-not (Test-Path -LiteralPath $ref)) { throw "Missing installed SSIS16 SDK reference: $ref" } }
$exe = Join-Path $evidence 'BuildCoffeePackage.exe'
$compileArgs = @('/nologo','/target:exe','/platform:x64',"/out:$exe") + @($refs | ForEach-Object { "/reference:$_" }) + @((Join-Path $PSScriptRoot 'BuildCoffeePackage.cs'))
& 'C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe' @compileArgs
if($LASTEXITCODE -ne 0) { throw 'SSIS builder compilation failed' }
& $exe $PSScriptRoot (Resolve-Path -LiteralPath $SourceFile).Path
if($LASTEXITCODE -ne 0) { throw 'SSIS package build failed' }
# Project.SaveTo assigns a fresh package VersionGUID. Publish that exact native
# package alongside the archive, rather than two otherwise-identical versions.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive=[IO.Compression.ZipFile]::OpenRead((Join-Path $PSScriptRoot 'CoffeeETLTrang.ispac'))
try {
 foreach($name in @('LoadCoffeeTrang.dtsx','SCD_TN04_Trang.dtsx','Project.params')) {
  $inputStream=$archive.GetEntry($name).Open()
  $outputStream=[IO.File]::Create((Join-Path $PSScriptRoot $name))
  try { $inputStream.CopyTo($outputStream) } finally { $inputStream.Dispose(); $outputStream.Dispose() }
 }
} finally { $archive.Dispose() }
& (Join-Path $PSScriptRoot 'Sync-CoffeeETLProject.ps1') -ProjectFolder $PSScriptRoot
if($LASTEXITCODE -ne 0) { throw 'Project descriptor sync failed' }
