#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Command = if ($args.Count -gt 0) { $args[0] } else { 'setup' }
if (@('setup', 'analysis-setup', 'verify-analysis', 'build', 'check', 'npm', 'node', 'rea') -notcontains $Command) {
    throw 'Expected setup, analysis-setup, verify-analysis, build, check, npm, node, or rea.'
}
$NpmArguments = @($args | Select-Object -Skip 1)
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This fork requires Windows x64.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    # GitHub Desktop need not register its bundled Git on the system PATH.
    $desktopRoot = Join-Path $env:LOCALAPPDATA 'GitHubDesktop'
    $desktopGit = $null
    if (Test-Path -LiteralPath $desktopRoot) {
        $desktopGit = Get-ChildItem -LiteralPath $desktopRoot -Directory -Filter 'app-*' |
            Sort-Object LastWriteTime -Descending |
            ForEach-Object { Join-Path $_.FullName 'resources\app\git\cmd\git.exe' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
    }
    if (-not $desktopGit) { throw 'Install Git or GitHub Desktop before running Windows setup.' }
    $env:PATH = (Split-Path -Parent $desktopGit) + ';' + $env:PATH
}
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$nodeVersion = (Get-Content -LiteralPath (Join-Path $repositoryRoot '.nvmrc') -Encoding utf8 -Raw).Trim()
$package = Get-Content -LiteralPath (Join-Path $repositoryRoot 'package.json') -Encoding utf8 -Raw | ConvertFrom-Json
if ($nodeVersion -notmatch '^\d+\.\d+\.\d+$' -or $package.packageManager -notmatch '^npm@(\d+\.\d+\.\d+)$') {
    throw 'Expected exact Node and npm versions in .nvmrc and package.json.'
}
$npmVersion = $Matches[1]
$toolRoot = Join-Path $repositoryRoot '.cache\windows-toolchain'
$nodeRoot = Join-Path $toolRoot "node-v$nodeVersion-win-x64"
$nodeExe = Join-Path $nodeRoot 'node.exe'
New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $nodeExe)) {
    $archive = Join-Path $toolRoot "node-v$nodeVersion-win-x64.zip"
    Write-Host "Downloading pinned Node $nodeVersion into this checkout."
    Invoke-WebRequest -UseBasicParsing -Uri "https://nodejs.org/dist/v$nodeVersion/node-v$nodeVersion-win-x64.zip" -OutFile $archive -TimeoutSec 180
    Expand-Archive -LiteralPath $archive -DestinationPath $toolRoot
}
$actualNode = & $nodeExe --version
if ($LASTEXITCODE -ne 0 -or $actualNode -ne "v$nodeVersion") {
    throw 'The project-local Node installation does not match .nvmrc.'
}
$npmPrefix = Join-Path $toolRoot "npm-$npmVersion"
$npmRoot = Join-Path $npmPrefix 'node_modules\npm'
$npmCli = Join-Path $npmRoot 'bin\npm-cli.js'
$env:PATH = $nodeRoot + ';' + $env:PATH
if (-not (Test-Path -LiteralPath $npmCli)) {
    & $nodeExe (Join-Path $nodeRoot 'node_modules\npm\bin\npm-cli.js') install --prefix $npmPrefix --no-save --no-package-lock --no-audit --no-fund "npm@$npmVersion"
    if ($LASTEXITCODE -ne 0) { throw 'Pinned npm installation failed.' }
}
$actualNpm = & $nodeExe $npmCli --version
if ($LASTEXITCODE -ne 0 -or $actualNpm -ne $npmVersion) {
    throw 'The project-local npm installation does not match packageManager.'
}
# Use npm's generated Windows shims; its internal bin directory is not a prefix.
$env:PATH = (Join-Path $npmPrefix 'node_modules\.bin') + ';' + $env:PATH
$analysisEnvironment = Join-Path $repositoryRoot '.cache\windows-analysis-tools\environment.json'
if ($Command -ne 'analysis-setup' -and (Test-Path -LiteralPath $analysisEnvironment -PathType Leaf)) {
    $analysis = Get-Content -LiteralPath $analysisEnvironment -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($name in @('GHIDRA_INSTALL_DIR', 'JAVA_HOME')) {
        $selected = $analysis.$name
        # Caller-selected tool paths take precedence over the local defaults.
        if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
            if (-not (Test-Path -LiteralPath $selected -PathType Container)) { throw "Missing project analysis tool: $selected" }
            [Environment]::SetEnvironmentVariable($name, $selected, 'Process')
        }
    }
}

function Invoke-Npm {
    param([string[]]$Arguments)
    & $nodeExe $npmCli @Arguments
    if ($LASTEXITCODE -ne 0) { throw "npm $($Arguments -join ' ') failed (exit $LASTEXITCODE)." }
}

function Build-WindowsArtifacts {
    Invoke-Npm @('run', 'build:windows-native')
    Invoke-Npm @('run', 'build:windows-native', '--', '--inspection-fixture')
    Invoke-Npm @('run', 'build:windows-native', '--', '--process-fixture')
    Invoke-Npm @('run', 'build:windows-native', '--', '--analysis-fixture')
    Invoke-Npm @('run', 'build:cached')
}

Push-Location -LiteralPath $repositoryRoot
try {
    Write-Host "Using project-local Node $nodeVersion and npm $npmVersion."
    switch ($Command) {
        'setup' {
            Invoke-Npm @('ci', '--no-audit', '--no-fund')
            Build-WindowsArtifacts
            Invoke-Npm @('run', 'verify:windows-native:artifact')
        }
        'analysis-setup' {
            & (Join-Path $PSScriptRoot 'setup-windows-analysis.ps1')
        }
        'verify-analysis' {
            & $nodeExe (Join-Path $PSScriptRoot 'build-windows-native.mjs') --analysis-fixture
            if ($LASTEXITCODE -ne 0) { throw 'Analysis sample compilation failed.' }
            Invoke-Npm @('run', 'verify:windows-analysis')
        }
        'build' {
            Build-WindowsArtifacts
        }
        'check' {
            Invoke-Npm @('run', 'check:windows')
        }
        'npm' {
            if ($NpmArguments.Count -eq 0) { throw 'Supply npm arguments after the npm command.' }
            Invoke-Npm $NpmArguments
        }
        'rea' {
            & $nodeExe (Join-Path $PSScriptRoot 'rea.mjs') @NpmArguments
            if ($LASTEXITCODE -ne 0) { throw "REA failed (exit $LASTEXITCODE)." }
        }
        'node' {
            & $nodeExe @NpmArguments
            if ($LASTEXITCODE -ne 0) { throw "Node command failed (exit $LASTEXITCODE)." }
        }
    }
} finally {
    Pop-Location
}
