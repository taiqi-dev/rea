#Requires -Version 7.0
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') {
    throw 'This checkout helper requires Windows and PowerShell 7.'
}
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

function Invoke-Git {
    param([string]$Directory, [string[]]$Arguments)
    $output = & git -C $Directory @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git failed in $Directory (exit $LASTEXITCODE): $($Arguments -join ' ')"
    }
    $output
}

$gitRoot = Invoke-Git $repositoryRoot @('rev-parse', '--show-toplevel')
if ((Resolve-Path -LiteralPath $gitRoot).Path -ne $repositoryRoot) {
    throw 'Run this helper from a REA checkout, not a directory inside another repository.'
}

# Preflight both worktrees before changing either one. An empty failed checkout
# is recoverable; any staged, unstaged, or untracked user content must be kept.
$modules = foreach ($name in @('unblob', 'wakaru')) {
    $path = "third_party/$name"
    $directory = Join-Path $repositoryRoot $path
    $contents = @(if (Test-Path -LiteralPath $directory) {
        Get-ChildItem -LiteralPath $directory -Force
    })
    $emptyCheckout = @($contents | Where-Object Name -ne '.git').Count -eq 0
    $initialized = Test-Path -LiteralPath (Join-Path $directory '.git')
    if ($initialized) {
        $moduleRoot = Invoke-Git $directory @('rev-parse', '--show-toplevel')
        if ((Resolve-Path -LiteralPath $moduleRoot).Path -ne $directory) {
            throw "Unexpected submodule worktree: $path"
        }
        $changes = @(Invoke-Git $directory @('status', '--porcelain', '--untracked-files=all', '--ignored'))
        $indexEntries = @(Invoke-Git $directory @('ls-files', '--sparse'))
        if ($changes.Count -gt 0 -and -not ($emptyCheckout -and $indexEntries.Count -eq 0)) {
            throw "$path has local changes or ignored files. Preserve them before rerunning this helper."
        }
    } elseif (-not $emptyCheckout) {
        throw "$path contains files but is not an initialized submodule."
    }
    [pscustomobject]@{
        Name = $name
        Path = $path
        Directory = $directory
        Initialized = $initialized
        EmptyCheckout = $emptyCheckout
    }
}

$backupPath = Invoke-Git $repositoryRoot @('rev-parse', '--path-format=absolute', '--git-path', "windows-submodule-backups/$([guid]::NewGuid())")
New-Item -ItemType Directory -Path $backupPath | Out-Null
function Backup-GitSettings {
    param([string]$Directory, [string]$Name)
    foreach ($file in @('config', 'config.worktree', 'HEAD', 'index', 'info/sparse-checkout')) {
        $source = Invoke-Git $Directory @('rev-parse', '--path-format=absolute', '--git-path', $file)
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $backupPath "$Name-$($file.Replace('/', '-'))")
        }
    }
}
Backup-GitSettings $repositoryRoot 'rea'

foreach ($module in $modules) {
    if (-not $module.Initialized) {
        $sourceUrl = Invoke-Git $repositoryRoot @('config', '--file', '.gitmodules', '--get', "submodule.$($module.Path).url")
        $sourceUrl = Invoke-Git $repositoryRoot @('config', '--default', $sourceUrl, '--get', "submodule.$($module.Path).url")
        $gitDirectory = Invoke-Git $repositoryRoot @('rev-parse', '--path-format=absolute', '--git-path', "modules/$($module.Path)")
        if (Test-Path -LiteralPath $gitDirectory) {
            throw "Unattached Git metadata exists at $gitDirectory; inspect it before retrying."
        }
        New-Item -ItemType Directory -Path (Split-Path $gitDirectory -Parent) -Force | Out-Null
        New-Item -ItemType Directory -Path (Split-Path $module.Directory -Parent) -Force | Out-Null
        # Download Git data first, before Windows sees incompatible fixture names.
        Invoke-Git $repositoryRoot @('clone', '--no-checkout', '--separate-git-dir', $gitDirectory, '--', $sourceUrl, $module.Directory)
    }
    Backup-GitSettings $module.Directory $module.Name
    if ($module.Name -eq 'unblob') {
        $gitlink = Invoke-Git $repositoryRoot @('ls-tree', 'HEAD', '--', $module.Path)
        $fields = $gitlink -split '\s+', 4
        if ($fields.Count -ne 4 -or $fields[0] -ne '160000' -or $fields[1] -ne 'commit' -or $fields[3] -ne $module.Path) {
            throw "Missing pinned Git submodule entry: $($module.Path)"
        }
        $revision = $fields[2]
        $knownRevision = & git -C $module.Directory rev-parse --verify --quiet "${revision}^{commit}"
        if ($LASTEXITCODE -eq 1) {
            Invoke-Git $module.Directory @('fetch', '--quiet', 'origin', $revision)
        } elseif ($LASTEXITCODE -ne 0 -or $knownRevision -ne $revision) {
            throw "Could not verify the pinned commit for $($module.Path)."
        }
        $directories = @(Invoke-Git $module.Directory @('-c', 'core.quotePath=false', 'ls-tree', '-d', '--name-only', $revision) | Where-Object { $_ -ne 'tests' })
        $directories += @(Invoke-Git $module.Directory @('-c', 'core.quotePath=false', 'ls-tree', '-d', '--name-only', "${revision}:tests") | Where-Object { $_ -ne 'integration' } | ForEach-Object { "tests/$_" })
        Invoke-Git $module.Directory @('config', '--local', 'core.longpaths', 'true')
        # Cone mode plus a sparse index keeps Git from expanding the invalid
        # control characters, trailing dots/spaces, and long fixture paths.
        Invoke-Git $module.Directory (@('sparse-checkout', 'set', '--cone', '--sparse-index', '--') + $directories)
    }
    $updateArguments = @('submodule', 'update', '--init', '--checkout')
    if ($module.EmptyCheckout) {
        $updateArguments += '--force'
    }
    Invoke-Git $repositoryRoot ($updateArguments + @('--', $module.Path))
    $changes = @(Invoke-Git $module.Directory @('status', '--porcelain', '--untracked-files=all'))
    if ($changes.Count -gt 0) {
        throw "$($module.Path) is not clean after checkout; backups are at $backupPath."
    }
    if ($module.Name -eq 'unblob') {
        # Recursive pull/checkout can expand this sparse index even when no
        # gitlink changed. Explicit updates above still work for inactive modules.
        Invoke-Git $repositoryRoot @('config', '--local', 'submodule.third_party/unblob.active', 'false')
    }
    Write-Host "$($module.Path): ready at the revision pinned by REA."
}
Write-Host "Git settings backed up at $backupPath. No analysis engines were installed."
