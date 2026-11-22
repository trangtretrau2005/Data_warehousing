param([string]$Database='CoffeeDW_Trang_SSIS_TN03_20261120')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python=Join-Path $root '.venv/Scripts/python.exe'
& $python (Join-Path $PSScriptRoot 'Prepare-Acceptance.py') --database $Database
if($LASTEXITCODE -ne 0){throw 'Fixture metadata preparation failed'}
$evidence=Join-Path $root 'results/native_build_20261120/ssis/acceptance_prepared'
New-Item -ItemType Directory -Path $evidence -Force|Out-Null
$exe=Join-Path $evidence 'BuildAcceptance.exe'
$refs=@('C:/Windows/Microsoft.NET/assembly/GAC_MSIL/Microsoft.SqlServer.ManagedDTS/v4.0_16.0.0.0__89845dcd8080cc91/Microsoft.SqlServer.ManagedDTS.dll','C:/Program Files/Microsoft SQL Server/160/DTS/Tasks/Microsoft.SqlServer.SQLTask.dll')
$compile=@('/nologo','/target:exe','/platform:x64',"/out:$exe")+@($refs|ForEach-Object{"/reference:$_"})+@((Join-Path $PSScriptRoot 'BuildAcceptance.cs'))
& 'C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe' @compile
if($LASTEXITCODE -ne 0){throw 'Acceptance builder compilation failed'}
$template=(Resolve-Path (Join-Path $PSScriptRoot '../CoffeeETLTrang/LoadCoffeeTrang.dtsx')).Path
& $exe $PSScriptRoot $template (Join-Path $PSScriptRoot 'acceptance_inputs.xml')
if($LASTEXITCODE -ne 0){throw 'Acceptance SDK build failed'}
& $python (Join-Path $PSScriptRoot 'Finish-Project.py')
if($LASTEXITCODE -ne 0){throw 'Descriptor/metadata verification failed'}
