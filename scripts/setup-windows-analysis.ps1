#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Analysis tool setup requires Windows x64.'
}
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$toolRoot = Join-Path $repositoryRoot '.cache\windows-analysis-tools'
$ghidraHome = if ($env:GHIDRA_INSTALL_DIR) { $env:GHIDRA_INSTALL_DIR } else { Join-Path $toolRoot 'ghidra_12.1.4_PUBLIC' }
$javaHome = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { Join-Path $toolRoot 'jdk-21.0.12.1+1' }
New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null

function Install-Archive {
    param([string]$Url, [string]$ArchiveName, [long]$Length, [string]$InstallationRoot, [string]$Marker)
    if (Test-Path -LiteralPath (Join-Path $InstallationRoot $Marker) -PathType Leaf) { return }
    if (Test-Path -LiteralPath $InstallationRoot) {
        throw "Incomplete installation at $InstallationRoot. Preserve and inspect it before retrying."
    }
    $archive = Join-Path $toolRoot $ArchiveName
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or (Get-Item -LiteralPath $archive).Length -ne $Length) {
        Write-Host "Downloading official archive $ArchiveName into this checkout."
        & curl.exe --fail --location --silent --show-error --connect-timeout 30 --max-time 900 --output $archive $Url
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $ArchiveName (exit $LASTEXITCODE)." }
    }
    if ((Get-Item -LiteralPath $archive).Length -ne $Length) { throw "Incomplete archive: $archive" }
    & tar.exe -xf $archive -C $toolRoot
    if ($LASTEXITCODE -ne 0) { throw "Archive extraction failed: $archive" }
    if (-not (Test-Path -LiteralPath (Join-Path $InstallationRoot $Marker) -PathType Leaf)) {
        throw "Archive did not produce its expected installation: $InstallationRoot"
    }
}

# Pinned official release archives. This opt-in source-checkout command does
# not install an MSI, modify PATH, or change REA's bring-your-own engine setup.
if (-not $env:GHIDRA_INSTALL_DIR) {
    Install-Archive 'https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip' 'ghidra_12.1.4_PUBLIC_20260921.zip' 569649598 $ghidraHome 'Ghidra\application.properties'
}
if (-not $env:JAVA_HOME) {
    Install-Archive 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip' 'OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip' 205073461 $javaHome 'bin\javac.exe'
}
$env:GHIDRA_INSTALL_DIR = $ghidraHome
$env:JAVA_HOME = $javaHome
$nodeVersion = (Get-Content -LiteralPath (Join-Path $repositoryRoot '.nvmrc') -Raw -Encoding utf8).Trim()
$node = Join-Path $repositoryRoot ".cache\windows-toolchain\node-v$nodeVersion-win-x64\node.exe"
if (-not (Test-Path -LiteralPath $node)) { throw 'Run scripts/windows.ps1 setup first.' }
& $node (Join-Path $PSScriptRoot 'rea.mjs') doctor --provider ghidra --json
if ($LASTEXITCODE -ne 0) { throw 'Downloaded Ghidra/JDK failed REA provider validation.' }
@{ GHIDRA_INSTALL_DIR = $ghidraHome; JAVA_HOME = $javaHome } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $toolRoot 'environment.json') -Encoding utf8
Write-Host 'Ghidra/JDK validated. The Windows command wrapper will load these project-local paths.'
