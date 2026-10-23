# Builds one prefab per Blender model with its materials saved as assets (Opus.Editor.ModelPrefabs): Assets/Opus/Prefabs/Models.
# Usage: powershell -ExecutionPolicy Bypass -File tools/Prefabs.ps1   (tools/Verify.ps1 runs it before the tests; every build too)
param([string]$UnityPath)
. (Join-Path $PSScriptRoot '_common.ps1')

$unity = Get-UnityEditorPath $UnityPath
Assert-ProjectClosed
$code = Invoke-Unity -Unity $unity -Arguments @('-quit', '-executeMethod', 'Opus.Editor.ModelPrefabs.Generate') -LogName 'unity-prefabs.log'
if ($code -ne 0) { throw 'Prefab generation failed; see Logs\unity-prefabs.log.' }
Show-UnityLogSummary (Join-Path $LogRoot 'unity-prefabs.log')
