param(
    [Parameter(Mandatory)][string]$MapPath,
    [Parameter(Mandatory)][string]$BinaryPath,
    [Parameter(Mandatory)][string]$DumpbinPath,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [string[]]$Types = @('Beach', 'Brush', 'Ground', 'Readback', 'Shovel', 'Water', 'Compute')
)

$ErrorActionPreference = 'Stop'
$map = Get-Content -LiteralPath $MapPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($map.source -ne $BinaryPath) { throw 'Binary path differs from mapped source.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
foreach ($method in $map.selected_methods) {
    if ($method.type -notin $Types -or $null -eq $method.unwind_entry_range) { continue }
    $range = '/RANGE:' + $method.unwind_entry_range[0] + ',' + $method.unwind_entry_range[1]
    $section = '/SECTION:' + $method.pointer_section
    $stem = '{0}_{1}_{2:x}' -f $method.type, $method.method, [int]$method.rid
    $stem = $stem -replace '[^a-zA-Z0-9_.-]', '_'
    $output = Join-Path $OutputDirectory ($stem + '.txt')
    & $DumpbinPath '/DISASM:NOBYTES' $range $section $BinaryPath | Set-Content -LiteralPath $output -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "dumpbin failed for $stem ($LASTEXITCODE)" }
    Write-Output $output
}
