# The look-dev scene (tools/blender/lookdev.py): lineups at true scale beside a 1.8 m person in neutral and game light,
# material spheres, 64/32 px silhouettes -> Builds/Style/lookdev/. Style.py bible puts them into the art bible.
# Usage: powershell -ExecutionPolicy Bypass -File tools/LookDev.ps1 [-BlenderPath <blender.exe>]
param([string]$BlenderPath)
. (Join-Path $PSScriptRoot '_common.ps1')

$blender = Get-BlenderPath $BlenderPath
$log = Join-Path $LogRoot 'blender-lookdev.log'
$process = Start-Process -FilePath $blender -ArgumentList @('-b', '--factory-startup', '--python-exit-code', '1', '--python',
    (Format-Arg (Join-Path $PSScriptRoot 'blender\lookdev.py'))) -NoNewWindow -Wait -PassThru -RedirectStandardOutput $log `
    -RedirectStandardError "$log.err"
Select-String -LiteralPath $log -Pattern '^\[Opus\]' | ForEach-Object { Write-Host ('  ' + $_.Line) }
if ($process.ExitCode -ne 0) { Get-Content -LiteralPath "$log.err" -Tail 20 | ForEach-Object { Write-Host "  $_" }; throw "Look-dev failed; see $log" }
