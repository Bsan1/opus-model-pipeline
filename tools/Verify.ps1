# One command for the whole check, with short output (21 October 2026: the separate steps printed hundreds of lines per run).
# Rebuilds only the models whose inputs changed (generator, opus_model.py, qc.py, outside assets, source textures), several at
# a time; runs the pipeline checks when the shared code changed; then Unity tests, the exe and the scenarios when anything the
# game uses changed. Prints one line per model, per step and per scenario; full logs stay in Logs\verify-*.log.
# Usage: powershell -ExecutionPolicy Bypass -File tools/Verify.ps1 [-Models house,shed] [-AllModels] [-Scenarios u16_showroom]
#        [-AllScenarios] [-NoUnity] [-Parallel 3]
#        [-Accept]: record the current inputs as built without building (after the models were built some other way)
#        [-Approve house,shed [-By name]]: record the user's approval of those models as they are now (their geometry hash)
#        [-Stats]: per model: builds, failures, review findings (from Builds\QC\history.jsonl and tools\blender\reviews)
# Scenarios when none are named: all of them after a change to the game's code (scripts, shaders, scenes, settings, packages),
# the three that show the models (u11_props, u16_models, u16_showroom) when only models or textures changed.
# Every model line ends with its approval state: a build that passes the gates is technically sound, not approved. A model is
# "approved" when the user approved exactly this geometry; a complex model (its plan's tier) "needs review" until an
# independent review of this geometry exists (.claude/skills/model-plausibility).
param([string[]]$Models, [switch]$AllModels, [string[]]$Scenarios, [switch]$AllScenarios, [switch]$NoUnity,
    [int]$Parallel = 3, [switch]$Accept, [string[]]$Approve, [string]$By = 'user', [switch]$Stats)
. (Join-Path $PSScriptRoot '_common.ps1')

$blenderDir = Join-Path $PSScriptRoot 'blender'
$statePath = Join-Path $ProjectRoot 'Builds\QC\verify-inputs.json'
$historyPath = Join-Path $ProjectRoot 'Builds\QC\history.jsonl'
$approvalsPath = Join-Path $blenderDir 'approvals.json'
$reviewsDir = Join-Path $blenderDir 'reviews'
New-Item -ItemType Directory -Path (Join-Path $ProjectRoot 'Builds\QC') -Force | Out-Null

function Read-JsonTable([string]$Path) {
    $table = @{}
    if (Test-Path -LiteralPath $Path) {
        (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $table[$_.Name] = $_.Value }
    }
    return $table
}
$state = Read-JsonTable $statePath

# Content hashes: a file counts as changed only when its bytes change (a checkout or copy that only touches the time does
# not rebuild). Each file is hashed once and remembered by path, size and time in Builds\QC\verify-filehashes.json.
$fileCachePath = Join-Path $ProjectRoot 'Builds\QC\verify-filehashes.json'
$fileCache = Read-JsonTable $fileCachePath
$fileCacheUsed = @{}
$sha = [System.Security.Cryptography.SHA256]::Create()
function Get-FileContentHash($File) {
    $key = "$($File.FullName)|$($File.Length)|$($File.LastWriteTimeUtc.Ticks)"
    if (-not $fileCache.ContainsKey($key)) {
        $stream = [System.IO.File]::OpenRead($File.FullName)
        try { $fileCache[$key] = [System.BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').Substring(0, 16) }
        finally { $stream.Dispose() }
    }
    $fileCacheUsed[$key] = $fileCache[$key]
    return $fileCache[$key]
}

function Get-InputsHash([string[]]$Paths) {
    # Path (relative to the project) and content of every file: a changed, added or removed input changes the hash
    $text = New-Object System.Text.StringBuilder
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        # (source_textures\generated is written by the generators themselves: an output, not an input)
        foreach ($file in @(Get-ChildItem -LiteralPath $path -Recurse -File -ErrorAction SilentlyContinue |
                    Where-Object { $_.FullName -notmatch '\\generated\\' } | Sort-Object FullName)) {
            [void]$text.Append("$($file.FullName.Substring($ProjectRoot.Length))|$(Get-FileContentHash $file)`n")
        }
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text.ToString())
    return [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').Substring(0, 16)
}

function Save-State {
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    $fileCacheUsed | ConvertTo-Json | Set-Content -LiteralPath $fileCachePath -Encoding UTF8
}

function Get-Spec([string]$Name) {
    $path = Join-Path $ProjectRoot "Assets\Opus\ModelSpecs\$Name.json"
    if (Test-Path -LiteralPath $path) { return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json }
    return $null
}

# Approval and review state: one implementation, in tools/Review.py (tested by tools/tests/test_review.py)
function Get-ReviewStates([string[]]$Names) {
    $text = & py -3 (Join-Path $PSScriptRoot 'Review.py') state @Names --json
    $states = @{}
    ($text | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $states[$_.Name] = $_.Value }
    return $states
}

function Get-ApprovalState([string]$Name) { return (Get-ReviewStates @($Name))[$Name].text }

if ($Approve) {
    & py -3 (Join-Path $PSScriptRoot 'Review.py') approve @($Approve | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) --by $By
    if ($LASTEXITCODE -ne 0) { exit 1 }
    return
}

if ($Stats) {
    # Builds and failures per model from the history; findings per review (stage: preview = before detailing)
    $rows = @{}
    if (Test-Path -LiteralPath $historyPath) {
        foreach ($line in Get-Content -LiteralPath $historyPath -Encoding UTF8) {
            if (-not $line.Trim()) { continue }
            $entry = $line | ConvertFrom-Json
            if (-not $rows.ContainsKey($entry.model)) { $rows[$entry.model] = @{ builds = 0; failed = 0; last = '' } }
            $rows[$entry.model].builds++
            if (-not $entry.ok) { $rows[$entry.model].failed++; $rows[$entry.model].last = $entry.reason }
        }
    }
    foreach ($name in @($rows.Keys | Sort-Object)) {
        $review = Join-Path $reviewsDir "$name.json"
        $findings = ''
        if (Test-Path -LiteralPath $review) {
            $r = Get-Content -LiteralPath $review -Raw -Encoding UTF8 | ConvertFrom-Json
            $groups = @($r.findings | Group-Object status | ForEach-Object { "$($_.Count) $($_.Name)" }) -join ', '
            $findings = "  review ($($r.stage)): $groups"
        }
        $last = if ($rows[$name].last) { "  last failure: $($rows[$name].last.Substring(0, [Math]::Min(90, $rows[$name].last.Length)))" } else { '' }
        Write-Host ('{0,-12} builds {1}, failed {2}{3}{4}' -f $name, $rows[$name].builds, $rows[$name].failed, $findings, $last)
    }
    return
}

$shared = @((Join-Path $blenderDir 'opus_model.py'), (Join-Path $blenderDir 'qc.py'), (Join-Path $blenderDir 'external'),
    (Join-Path $blenderDir 'source_textures'))
$all = @(Get-ChildItem -LiteralPath (Join-Path $blenderDir 'models') -Filter '*.py' | ForEach-Object { $_.BaseName } | Sort-Object)
# The mower places wheel.fbx; house and shed both rewrite Tiling/tiling.json: these go one after the other
$after = @{ 'mower' = 'wheel'; 'shed' = 'house' }
$hashes = @{}
foreach ($name in $all) {
    $inputs = $shared + @(Join-Path $blenderDir "models\$name.py")
    if ($after.ContainsKey($name)) { $inputs += Join-Path $blenderDir "models\$($after[$name]).py" }
    $hashes[$name] = Get-InputsHash $inputs
}
if ($Accept) {
    foreach ($name in $all) { $state[$name] = $hashes[$name] }
    Save-State
    Write-Host "Accepted the current inputs of $($all.Count) models as built"
    return
}
if ($AllModels) { $todo = $all }
elseif ($Models) { $todo = @($Models | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) }
else {
    $todo = @($all | Where-Object {
            -not $state.ContainsKey($_) -or $state[$_] -ne $hashes[$_] -or
            -not (Test-Path -LiteralPath (Join-Path $ProjectRoot "Assets\Opus\Resources\Models\$_.fbx")) })
}

$failed = @()

function Invoke-Step([string]$Script, [string[]]$Arguments, [string]$Log) {
    # A child script's stderr must not stop this one (_common.ps1 sets ErrorActionPreference = Stop); everything goes to the log
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $Script) @Arguments *> $Log
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    return $code
}

function Test-EditorOpen {
    $lock = Join-Path $ProjectRoot 'Temp\UnityLockfile'
    if (-not (Test-Path -LiteralPath $lock)) { return $false }
    try { ([System.IO.File]::Open($lock, 'Open', 'ReadWrite', 'None')).Close(); return $false } catch { return $true }
}

function Write-ModelLine([string]$Name, [int]$Code, [double]$Seconds, [datetime]$Started) {
    $qcPath = Join-Path $ProjectRoot "Builds\QC\$Name.json"
    $bits = @()
    if (Test-Path -LiteralPath $qcPath) {
        $qc = Get-Content -LiteralPath $qcPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($qc.zFighting) { $bits += "zf $($qc.zFighting.pairs)" }
        if ($qc.holes) { $bits += "holes $($qc.holes.backface_hits)" }
        if ($qc.joints) { $bits += "joints $($qc.joints.bad)" }
        if ($qc.texels) { $bits += "thin $($qc.texels.thin_faces)" }
        if ($qc.construction) { $bits += "loose $(@($qc.construction.stray).Count), links $(@($qc.construction.problems).Count)" }
    }
    $entry = [ordered]@{ time = (Get-Date -Format 's'); model = $Name; ok = ($Code -eq 0); seconds = [int]$Seconds; gates = ($bits -join ', ') }
    if ($Code -eq 0) {
        Add-Content -LiteralPath $historyPath -Value ($entry | ConvertTo-Json -Compress) -Encoding UTF8
        Write-Host ('  {0,-12} ok    {1}  {2:N0} s  [{3}]' -f $Name, ($bits -join ', '), $Seconds, (Get-ApprovalState $Name))
        return $true
    }
    # The reason: this build's Python exception (a gate's message carries its numbers), else what Models.ps1 threw
    $err = Join-Path $LogRoot "blender-$Name.err.log"
    $reason = ''
    $where = "Logs\blender-$Name.err.log"
    if ((Test-Path -LiteralPath $err) -and (Get-Item -LiteralPath $err).LastWriteTime -ge $Started) {
        $line = Select-String -LiteralPath $err -Pattern '^\w*(Error|Exception)\b' | Where-Object { $_.Line -notmatch '^Error: script failed' } | Select-Object -Last 1
        if ($line) { $reason = $line.Line.Trim() }
    }
    if (-not $reason) {
        $where = "Logs\verify-model-$Name.log.err"
        $line = Get-Content -LiteralPath (Join-Path $LogRoot "verify-model-$Name.log.err") -ErrorAction SilentlyContinue | Where-Object { $_.Trim() } | Select-Object -First 1
        if ($line) { $reason = $line.Trim() }
    }
    if ($reason.Length -gt 300) { $reason = $reason.Substring(0, 300) + '...' }
    $entry['reason'] = $reason
    Add-Content -LiteralPath $historyPath -Value ($entry | ConvertTo-Json -Compress) -Encoding UTF8
    Write-Host ('  {0,-12} FAIL  {1}  ({2})' -f $Name, $reason, $where)
    return $false
}

Write-Host ("Models: {0} to build ({1})" -f $todo.Count, ($(if ($todo.Count) { $todo -join ', ' } else { 'none changed' })))
$pending = New-Object System.Collections.ArrayList
$todo | ForEach-Object { [void]$pending.Add($_) }
$running = @{}
$done = @{}
$built = @()
while ($pending.Count -gt 0 -or $running.Count -gt 0) {
    foreach ($name in @($pending)) {
        if ($running.Count -ge $Parallel) { break }
        $before = $after[$name]
        if ($before -and (($pending -contains $before) -or $running.ContainsKey($before))) { continue }
        $log = Join-Path $LogRoot "verify-model-$name.log"
        $process = Start-Process -FilePath 'powershell' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            (Format-Arg (Join-Path $PSScriptRoot 'Models.ps1')), '-Only', $name) -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        $null = $process.Handle
        $running[$name] = @{ Process = $process; Watch = [Diagnostics.Stopwatch]::StartNew(); Started = Get-Date }
        $pending.Remove($name)
    }
    Start-Sleep -Milliseconds 500
    foreach ($name in @($running.Keys)) {
        $job = $running[$name]
        if (-not $job.Process.HasExited) { continue }
        $job.Process.WaitForExit()
        $ok = Write-ModelLine $name $job.Process.ExitCode $job.Watch.Elapsed.TotalSeconds $job.Started
        if ($ok) { $state[$name] = $hashes[$name]; $built += $name } else { $failed += "model $name" }
        $running.Remove($name)
    }
}

# Style: every model's base colours inside the art style (tools/Style.py, tools/blender/style/style.json; skill art-style)
if (Test-Path -LiteralPath (Join-Path $blenderDir 'style\style.json')) {
    $log = Join-Path $LogRoot 'verify-style.log'
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & py -3 (Join-Path $PSScriptRoot 'Style.py') report *> $log
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    $total = @(Select-String -LiteralPath $log -Pattern '^\S+\s+(ok|OUTSIDE)\s').Count
    $outside = @(Select-String -LiteralPath $log -Pattern '^\S+\s+OUTSIDE\s' | ForEach-Object { ($_.Line -split '\s+')[0] })
    $warned = @(Select-String -LiteralPath $log -Pattern '^\s+warning:').Count
    $note = if ($warned) { "; $warned warning(s) from rules that only report (Logs\verify-style.log)" } else { '' }
    if ($code -eq 0) { Write-Host "Style: $total/$total inside the style$note" }
    else { Write-Host "Style: outside: $($outside -join ', ') (Logs\verify-style.log)"; $failed += 'style' }
}

# Tool tests (review and approval integrity, no Blender): when the review tool or its tests changed
$toolsHash = Get-InputsHash @((Join-Path $PSScriptRoot 'Review.py'), (Join-Path $PSScriptRoot 'Compare.py'),
    (Join-Path $PSScriptRoot 'Style.py'), (Join-Path $PSScriptRoot 'tests'))
if ($state['_tools'] -ne $toolsHash) {
    $log = Join-Path $LogRoot 'verify-tooltests.log'
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & py -3 -m unittest discover -s (Join-Path $PSScriptRoot 'tests') *> $log
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    $ran = Select-String -LiteralPath $log -Pattern '^Ran (\d+) test' | Select-Object -First 1
    $count = if ($ran) { $ran.Matches[0].Groups[1].Value } else { '?' }
    if ($code -eq 0) { Write-Host "Tool tests: $count passed"; $state['_tools'] = $toolsHash }
    else { Write-Host "Tool tests: FAILED of $count (Logs\verify-tooltests.log)"; $failed += 'tool tests' }
}
else { Write-Host 'Tool tests: unchanged' }

# Pipeline checks: when the shared code or a check changed
$checksHash = Get-InputsHash @((Join-Path $blenderDir 'opus_model.py'), (Join-Path $blenderDir 'qc.py'), (Join-Path $blenderDir 'checks'))
if ($state['_checks'] -ne $checksHash) {
    $log = Join-Path $LogRoot 'verify-checks.log'
    $code = Invoke-Step 'Models.ps1' @('-Checks') $log
    $passed = @(Select-String -LiteralPath $log -Pattern '^Passed:').Count
    $total = @(Get-ChildItem -LiteralPath (Join-Path $blenderDir 'checks') -Filter '*.py').Count
    if ($code -eq 0 -and $passed -eq $total) { Write-Host "Checks: $passed/$total"; $state['_checks'] = $checksHash }
    else { Write-Host "Checks: $passed/$total FAILED (Logs\verify-checks.log)"; $failed += 'checks' }
}
else { Write-Host 'Checks: unchanged' }

Save-State

if (-not $NoUnity -and -not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'ProjectSettings'))) {
    # The standalone pipeline repository: tests, build and scenarios belong to the Unity project that uses the models
    Write-Host 'Unity: no Unity project here (tests, build and scenarios run in the game project)'
}
elseif (-not $NoUnity -and $failed.Count -eq 0 -and (Test-EditorOpen)) {
    Write-Host 'Unity: skipped, the editor has the project open (close it to run tests, build and scenarios)'
}
elseif (-not $NoUnity -and $failed.Count -eq 0) {
    $code = @('Scripts', 'Editor', 'Tests', 'Scenes', 'Resources\Shaders') | ForEach-Object { Join-Path $ProjectRoot "Assets\Opus\$_" }
    $code += @((Join-Path $ProjectRoot 'ProjectSettings'), (Join-Path $ProjectRoot 'Packages'))
    $codeHash = Get-InputsHash $code
    $unityHash = Get-InputsHash (@((Join-Path $ProjectRoot 'Assets\Opus')) + $code)
    $scenarioReason = 'named'
    if (-not $Scenarios) {
        if ($AllScenarios -or $state['_code'] -ne $codeHash) { $AllScenarios = $true; $scenarioReason = 'all: game code changed' }
        else { $Scenarios = @('u11_props', 'u16_models', 'u16_showroom'); $scenarioReason = 'the model scenarios' }
    }
    if ($state['_unity'] -eq $unityHash -and $built.Count -eq 0 -and $scenarioReason -eq 'the model scenarios') {
        Write-Host 'Unity: unchanged'
    }
    else {
        # One prefab per model (Opus.Editor.ModelPrefabs) before the tests check them
        $log = Join-Path $LogRoot 'verify-prefabs.log'
        if ((Invoke-Step 'Prefabs.ps1' @() $log) -ne 0) { Write-Host 'Prefabs: FAILED (Logs\verify-prefabs.log, Logs\unity-prefabs.log)'; $failed += 'prefabs' }
        else {
            $line = Select-String -LiteralPath (Join-Path $LogRoot 'unity-prefabs.log') -Pattern '\[Opus\] Model prefabs: \d+' | Select-Object -Last 1
            Write-Host ($(if ($line) { 'Prefabs: ' + ($line.Line -replace '.*Model prefabs: ', '') } else { 'Prefabs: ok' }))
        }
        $log = Join-Path $LogRoot 'verify-tests.log'
        $code = Invoke-Step 'Test.ps1' @('-Platform', 'EditMode') $log
        $line = Select-String -LiteralPath $log -Pattern '^Tests:' | Select-Object -First 1
        Write-Host ($(if ($line) { $line.Line } else { 'Tests: no result (Logs\verify-tests.log)' }))
        foreach ($f in @(Select-String -LiteralPath $log -Pattern 'FAILED:' -Context 0, 1 | Select-Object -First 8)) {
            Write-Host ('  ' + $f.Line.Trim() + ' :: ' + ($f.Context.PostContext -join ' ').Trim())
        }
        $delivery = Join-Path $ProjectRoot 'Builds\QC\delivery.json'
        if ((Test-Path -LiteralPath $delivery) -and (Get-Item -LiteralPath $delivery).LastWriteTime -gt (Get-Item -LiteralPath $log).CreationTime) {
            # Measured by ModelImportTests.DeliveryCostsAreMeasured: what the models cost once imported
            # (no @() round the pipe: Windows PowerShell passes a JSON array on as one object, and @() would nest it)
            $rows = Get-Content -LiteralPath $delivery -Raw -Encoding UTF8 | ConvertFrom-Json
            $tris = ($rows | Measure-Object triangles -Sum).Sum
            $uv = ($rows | Measure-Object unityVertices -Sum).Sum
            $bv = ($rows | Measure-Object blenderVertices -Sum).Sum
            $calls = ($rows | Measure-Object drawCalls -Sum).Sum
            Write-Host ('Delivery: {0:N0} tris, {1:N0} vertices in Unity ({2:N2} x Blender''s {3:N0}), {4} draw calls, {5} models' -f
                $tris, $uv, ($uv / [Math]::Max(1, $bv)), $bv, $calls, @($rows | Select-Object -ExpandProperty model -Unique).Count)
        }
        if ($code -ne 0) { $failed += 'tests' }
        else {
            $log = Join-Path $LogRoot 'verify-build.log'
            if ((Invoke-Step 'Build.ps1' @() $log) -ne 0) { Write-Host 'Build: FAILED (Logs\verify-build.log)'; $failed += 'build' }
            else {
                Write-Host 'Build: ok'
                if ($AllScenarios) {
                    $source = Get-Content -LiteralPath (Join-Path $ProjectRoot 'Assets\Opus\Scripts\Core\Scenarios.cs') -Raw -Encoding UTF8
                    $Scenarios = @([regex]::Matches($source, '\["(u\d+_[a-z_]+)"\] =') | ForEach-Object { $_.Groups[1].Value })
                }
                $passedScenarios = 0
                foreach ($scenario in $Scenarios) {
                    $log = Join-Path $LogRoot "verify-scenario-$scenario.log"
                    if ((Invoke-Step 'Shots.ps1' @('-Scenario', $scenario, '-TimeoutSeconds', '600') $log) -eq 0) { $passedScenarios++ }
                    else {
                        $errors = @(Select-String -LiteralPath $log -Pattern 'ERROR|timed out|No report' | Select-Object -First 3 | ForEach-Object { $_.Line.Trim() })
                        Write-Host ("  {0} FAILED: {1}" -f $scenario, ($errors -join ' | '))
                        $failed += "scenario $scenario"
                    }
                }
                Write-Host ("Scenarios: {0}/{1} ({2})" -f $passedScenarios, $Scenarios.Count, $scenarioReason)
                if ($failed.Count -eq 0) {
                    $state['_unity'] = $unityHash
                    if ($AllScenarios) { $state['_code'] = $codeHash }
                    Save-State
                }
            }
        }
    }
}
# Game shots against the reference frames they recreate (Style.py shots, style.json in_game.pairs): warn only, because a
# difference here comes from the game's light and post-processing, not from one asset; when a shot or the style changed
$styleFile = Join-Path $blenderDir 'style\style.json'
$pairShots = @()
if (Test-Path -LiteralPath $styleFile) {
    $pairShots = @((Get-Content -LiteralPath $styleFile -Raw -Encoding UTF8 | ConvertFrom-Json).in_game.pairs |
        ForEach-Object { Join-Path $ProjectRoot $_.game } | Where-Object { Test-Path -LiteralPath $_ })
}
if ($pairShots.Count) {
    $shotsHash = Get-InputsHash (@($styleFile, (Join-Path $PSScriptRoot 'Style.py')) + $pairShots)
    if ($state['_shots'] -ne $shotsHash) {
        $log = Join-Path $LogRoot 'verify-shots.log'
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & py -3 (Join-Path $PSScriptRoot 'Style.py') shots *> $log
        $ErrorActionPreference = $previous
        $line = Select-String -LiteralPath $log -Pattern '^game shots: (.*)$' | Select-Object -First 1
        if ($line) { Write-Host "Game shots: $($line.Matches[0].Groups[1].Value) (Logs\verify-shots.log)"; $state['_shots'] = $shotsHash; Save-State }
        else { Write-Host 'Game shots: not measured (Logs\verify-shots.log)' }
    }
    else { Write-Host 'Game shots: unchanged' }
}
# Technical success is not approval: one line on what still waits for a review or for the user
# (approved with a warning - an open serious finding, a critical feature failing or unverified - is not counted as clean)
$states = Get-ReviewStates $all
$waiting = @($all | Where-Object { -not $states[$_].clean } | ForEach-Object { "$_ ($($states[$_].text))" })
if ($waiting.Count) { Write-Host ("Approval: {0}/{1} approved and clean; waiting: {2}" -f ($all.Count - $waiting.Count), $all.Count, ($waiting -join ', ')) }
else { Write-Host "Approval: all $($all.Count) approved and clean" }
if ($failed.Count) { Write-Host ("FAILED: " + ($failed -join ', ')); exit 1 }
Write-Host 'All passed'
