param([string]$Output=(Join-Path $PSScriptRoot '../../../results/native_build_20261120/ssis/readonly_diagnostics'))
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Path $Output -Force|Out-Null
$state=[ordered]@{CollectedLocal=(Get-Date).ToString('o');LastBoot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;Scope='Read-only OS/MSI/VS evidence. No restart/service/permission/license changes or debug-host execution.'}
$pending=@((Get-ItemProperty 'HKLM:/SYSTEM/CurrentControlSet/Control/Session Manager').PendingFileRenameOperations)
$state.PendingRenameEntries=$pending.Count
$state.PendingSSISOrConfigMsi=@($pending|Where-Object{$_ -match 'instapi160|sqlboot|SSDTIS|DataTransformation|SSIS|Config.Msi'}|Select-Object -First 40)
$paths=@('C:/Program Files/Microsoft SQL Server/160/Shared/instapi160.dll','C:/Program Files/Microsoft SQL Server/160/Shared/sqlboot.dll','C:/Program Files/Microsoft Visual Studio/18/Insiders/Common7/IDE/devenv.exe','C:/Program Files/Microsoft Visual Studio/18/Insiders/Common7/IDE/CommonExtensions/Microsoft/SSIS/160/Binn/DtsDebugHost.exe')
$state.FileVersions=@(foreach($path in $paths){if(Test-Path -LiteralPath $path){$f=Get-Item -LiteralPath $path;[ordered]@{Path=$path;FileVersion=$f.VersionInfo.FileVersion;Length=$f.Length;LastWrite=$f.LastWriteTime;SHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}})
$setup=Join-Path $env:TEMP 'SsdtisSetup'
$state.InstallerEvidence=@()
foreach($file in (Get-ChildItem -LiteralPath $setup -File -Filter '*.log' -ErrorAction SilentlyContinue|Where-Object{$_.Name -match '_9_SSDTISSingleton160\.log$|\d{14}\.log$'})) {
 $matches=@(Select-String -LiteralPath $file.FullName -Pattern 'held in use|Scheduling reboot|restart: Required|restart: Required|Apply complete|restarting: No|instapi160.dll.*Overwrite|FileCopy.*instapi160|Exit code:.*restarting'|Select-Object -First 30|ForEach-Object{[ordered]@{LineNumber=$_.LineNumber;Line=$_.Line}})
 if($matches.Count){$state.InstallerEvidence+=@{Path=$file.FullName;SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant();Excerpts=$matches}}
}
$events=@(Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=(Get-Date).Date;Id=1000,1001} -MaxEvents 150 -ErrorAction SilentlyContinue|Where-Object{$_.Message -match 'devenv.exe|DtsDebugHost'}|Select-Object -First 12 TimeCreated,Id,ProviderName,Message)
$events|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $Output 'application_events.json') -Encoding UTF8
$state.Events=@($events|ForEach-Object{@{TimeCreated=$_.TimeCreated;Id=$_.Id;Provider=$_.ProviderName}})
$state.WERDetail='Detailed Report.wer read denied by Windows; no permission change attempted. Application Event1000/1001 were readable.'
$state|ConvertTo-Json -Depth 9|Set-Content -LiteralPath (Join-Path $Output 'environment.json') -Encoding UTF8
Write-Output ('Saved read-only diagnostic evidence: '+$Output)
