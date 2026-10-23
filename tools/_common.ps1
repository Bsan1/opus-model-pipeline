# Shared helpers: runs Unity without opening the editor window (batchmode).
$ErrorActionPreference = 'Stop'
$script:ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$script:LogRoot = Join-Path $ProjectRoot 'Logs'
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

function Get-UnityEditorPath {
    param([string]$Override)
    if ($Override) {
        if (Test-Path -LiteralPath $Override) { return $Override }
        throw "Unity not found: $Override"
    }
    $version = '6000.3.11f1'
    $versionFile = Join-Path $ProjectRoot 'ProjectSettings\ProjectVersion.txt'
    if (Test-Path -LiteralPath $versionFile) {
        $match = Select-String -LiteralPath $versionFile -Pattern '^m_EditorVersion:\s*(\S+)' | Select-Object -First 1
        if ($match) { $version = $match.Matches[0].Groups[1].Value }
    }
    foreach ($candidate in @(
            "C:\Program Files\Unity\Hub\Editor\$version-x86_64\Editor\Unity.exe",
            "C:\Program Files\Unity\Hub\Editor\$version\Editor\Unity.exe")) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw "Unity $version is not installed."
}

function Assert-ProjectClosed {
    $lock = Join-Path $ProjectRoot 'Temp\UnityLockfile'
    if (Test-Path -LiteralPath $lock) {
        try {
            $stream = [System.IO.File]::Open($lock, 'Open', 'ReadWrite', 'None')
            $stream.Close()
        }
        catch {
            throw 'The project is open in a Unity editor right now. Close the editor first.'
        }
    }
}

function Format-Arg([string]$Value) {
    if ($Value -match '[\s"]') { return '"' + $Value.Replace('"', '\"') + '"' }
    return $Value
}

function Show-UnityLogSummary([string]$LogPath) {
    if (-not (Test-Path -LiteralPath $LogPath)) { Write-Host "  (no log: $LogPath)"; return }
    $pattern = '\[Opus\]|error CS\d+|Compilation failed|compiler errors|Shader error|Exception:|Error building|BuildFailedException|Aborting batchmode'
    $lines = Select-String -LiteralPath $LogPath -Pattern $pattern | Select-Object -First 60
    foreach ($line in $lines) { Write-Host ('  ' + $line.Line.Trim()) }
}

function Invoke-Unity {
    param(
        [Parameter(Mandatory)] [string]$Unity,
        [string[]]$Arguments,
        [Parameter(Mandatory)] [string]$LogName,
        [int]$TimeoutMinutes = 30
    )
    $log = Join-Path $LogRoot $LogName
    $all = @('-batchmode', '-projectPath', $ProjectRoot, '-logFile', $log) + $Arguments
    $argLine = ($all | ForEach-Object { Format-Arg "$_" }) -join ' '

    Write-Host "Unity: $LogName ..."
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $Unity -ArgumentList $argLine -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
    $null = $process.Handle  # take the handle now so ExitCode can be read
    if (-not $process.WaitForExit($TimeoutMinutes * 60 * 1000)) {
        Stop-Process -Id $process.Id -Force
        throw "Unity timed out ($LogName)."
    }
    $process.WaitForExit()
    Write-Host ('Unity done: {0} (exit code {1}, {2:N0} s)' -f $LogName, $process.ExitCode, $watch.Elapsed.TotalSeconds)
    Show-UnityLogSummary $log
    return $process.ExitCode
}

# Blender (tools/Models.ps1, tools/LookDev.ps1): -BlenderPath, then $env:BLENDER, then the usual install folders
function Get-BlenderPath([string]$Override) {
    $candidates = @($Override, $env:BLENDER,
        'D:\Steam\steamapps\common\Blender\blender.exe',
        'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe')
    $candidates += @(Get-ChildItem 'C:\Program Files\Blender Foundation' -Filter blender.exe -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw 'Blender not found; pass -BlenderPath or set the BLENDER environment variable.'
}
