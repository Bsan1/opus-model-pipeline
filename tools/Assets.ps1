# Outside assets for the model pipeline through free-assets (the shared tool in ..\free-assets; it is also an MCP server).
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools/Assets.ps1 -Sources
#   powershell -ExecutionPolicy Bypass -File tools/Assets.ps1 -Search "watering can" [-Source polyhaven,ambientcg] [-Kind model] [-Limit 10]
#   powershell -ExecutionPolicy Bypass -File tools/Assets.ps1 -Get polyhaven:planter_pot_clay [-Resolution 1k] [-Format gltf] -ApprovedBy "user, 21 Oct 2026"
#   powershell -ExecutionPolicy Bypass -File tools/Assets.ps1 -Credits
# Files go to tools/blender/external/<source>/<id>/ with asset.json (source, licence, authors); assets.json and
# CREDITS.md in that folder list everything. Unity never sees the folder: a model generator imports the asset with
# om.external(...) and bakes it into the model's atlas. Licences allowed for the game: opus_model.EXTERNAL_LICENCES.
# Keys (Poly Pizza, Sketchfab, BlenderKit) are per user: `free-assets key set <source>` in a terminal (hidden prompt).
param([switch]$Sources, [string]$Search, [string]$Source, [string]$Kind, [int]$Limit = 10, [string[]]$Get,
    [string]$Resolution = '1k', [string]$Format, [string]$ApprovedBy = '', [switch]$Force, [switch]$Credits)
. (Join-Path $PSScriptRoot '_common.ps1')

$tool = if ($env:FREE_ASSETS_HOME) { $env:FREE_ASSETS_HOME } else { Join-Path $ProjectRoot '..\free-assets' }
if (-not (Test-Path -LiteralPath (Join-Path $tool 'free_assets\cli.py'))) {
    throw "free-assets not found at $tool; clone it there or set FREE_ASSETS_HOME."
}
$dest = Join-Path $ProjectRoot 'tools\blender\external'
$allowed = 'CC0,CC-BY,OGA-BY,BlenderKit-RF'   # same as EXTERNAL_LICENCES in tools/blender/opus_model.py
$env:PYTHONPATH = (Resolve-Path -LiteralPath $tool).Path
$env:PYTHONIOENCODING = 'utf-8'

function Invoke-FreeAssets([string[]]$Arguments) {
    # Notes come on stderr; Windows PowerShell must not turn them into terminating errors
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & py -3 -m free_assets @Arguments
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "free-assets $($Arguments[0]) failed (exit $code)" }
}

if (-not ($Sources -or $Search -or $Get -or $Credits)) {
    Get-Content -LiteralPath $PSCommandPath -TotalCount 9 | ForEach-Object { $_ -replace '^# ?', '' }
    return
}
if ($Sources) { Invoke-FreeAssets @('sources') }
if ($Search) {
    $cli = @('search', $Search, '-n', "$Limit", '-l', $allowed)
    if ($Source) { $cli += @('-s', $Source) }
    if ($Kind) { $cli += @('-k', $Kind) }
    Invoke-FreeAssets $cli
}
if ($Get) {
    $cli = @('get') + $Get + @('--dest', $dest, '-r', $Resolution, '--allow', $allowed)
    if ($Format) { $cli += @('-f', $Format) }
    if ($ApprovedBy) { $cli += @('--approved-by', $ApprovedBy) }
    if ($Force) { $cli += '--force' }
    Invoke-FreeAssets $cli
}
if ($Credits) { Invoke-FreeAssets @('credits', '--dest', $dest) }
