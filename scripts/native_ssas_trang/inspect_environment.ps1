param(
    [string]$Server = 'localhost\TRANGTRETRAU',
    [string]$Output = 'results/native_build_20261120/ssas/integrated_ssis_source/environment.json'
)
$ErrorActionPreference = 'Stop'
$clientRoot = 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
$script:identityAssembly = [System.Reflection.Assembly]::LoadFrom((Join-Path $clientRoot 'PrivateAssemblies\Microsoft.Identity.Client.dll'))
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
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.Core.dll')
Add-Type -Path (Join-Path $clientRoot 'Microsoft.AnalysisServices.dll')
$amo = New-Object Microsoft.AnalysisServices.Server
try {
    $amo.Connect("Data Source=$Server;Connect Timeout=15")
    $ownedCube = $amo.Databases.FindByName('CoffeeCube_Trang_20261120')
    $cubeMetadata = $null
    if ($null -ne $ownedCube) {
        $cube = $ownedCube.Cubes.FindByName('Coffee Performance')
        $inventory = if ($null -ne $cube -and $cube.MeasureGroups.Count -gt 0) { $cube.MeasureGroups[0].Measures.FindByName('Inventory') } else { $null }
        $cubeMetadata = [ordered]@{
            state = [string]$ownedCube.State
            inventory_aggregate = if ($null -ne $inventory) { [string]$inventory.AggregateFunction } else { $null }
            inventory_visible = if ($null -ne $inventory) { [bool]$inventory.Visible } else { $null }
            dimensions = @($ownedCube.Dimensions | ForEach-Object { [ordered]@{
                name = $_.Name
                key_duplicate = [string]$_.ErrorConfiguration.KeyDuplicate
                key_not_found = [string]$_.ErrorConfiguration.KeyNotFound
                null_key_not_allowed = [string]$_.ErrorConfiguration.NullKeyNotAllowed
                null_key_converted_to_unknown = [string]$_.ErrorConfiguration.NullKeyConvertedToUnknown
            } })
        }
    }
    $providers = [System.Data.OleDb.OleDbEnumerator]::GetRootEnumerator()
    $names = @()
    try {
        while ($providers.Read()) {
            if ($providers['SOURCES_NAME'] -match 'SQL|MSOLAP') {
                $names += [string]$providers['SOURCES_NAME']
            }
        }
    } finally { $providers.Close() }
    [xml]$ini = Get-Content -LiteralPath 'C:\Program Files\Microsoft SQL Server\MSAS17.TRANGTRETRAU\OLAP\Config\msmdsrv.ini'
    $report = [ordered]@{
        timestamp_utc = [DateTime]::UtcNow.ToString('o')
        inspection = 'read_only_AMO_connection_and_metadata_only'
        server = $Server
        connected = $amo.Connected
        version = $amo.Version
        server_mode = [string]$amo.ServerMode
        edition = $amo.Edition
        deployment_mode_config = [string]$ini.ConfigurationSettings.DeploymentMode
        databases = @($amo.Databases | ForEach-Object { [ordered]@{id=$_.ID;name=$_.Name;state=[string]$_.State} })
        owned_cube_metadata = $cubeMetadata
        local_ole_db_providers_64bit = $names
        amo_client_assembly = [Microsoft.AnalysisServices.Server].Assembly.FullName
        writes_executed = $false
    }
    $parent = Split-Path -Parent $Output
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $json = $report | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) $Output), $json, (New-Object System.Text.UTF8Encoding($false)))
    $json
} finally {
    if ($amo.Connected) { $amo.Disconnect() }
}
