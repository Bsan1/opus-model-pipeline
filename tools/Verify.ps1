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

function Get-ApprovalState([string]$Name) {
    # approved | approval outdated | reviewed | review: N open | review outdated | needs review | not approved
    $spec = Get-Spec $Name
    if (-not $spec -or -not $spec.geometry) { return 'not built' }
    $approvals = Read-JsonTable $approvalsPath
    if ($approvals.ContainsKey($Name) -and $approvals[$Name].geometry -eq $spec.geometry) { return 'approved' }
    $outdated = $approvals.ContainsKey($Name)
    $reviewPath = Join-Path $reviewsDir "$Name.json"
    $review = if (Test-Path -LiteralPath $reviewPath) { Get-Content -LiteralPath $reviewPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    if ($review -and $review.geometry -eq $spec.geometry) {
        $open = @($review.findings | Where-Object { $_.status -eq 'open' }).Count
        $text = if ($open) { "review: $open open" } else { 'reviewed' }
    }
    elseif ($review) { $text = 'review outdated' }
    elseif ($spec.plan -and $spec.plan.tier -eq 'complex') { $text = 'needs review' }
    else { $text = 'not approved' }
    if ($outdated) { $text += ', approval outdated' }
    return $text
}

if ($Approve) {
    $approvals = Read-JsonTable $approvalsPath
    foreach ($name in @($Approve | ForEach-Object { $_ -split ',' } | Where-Object { $_ })) {
        $spec = Get-Spec $name
        if (-not $spec -or -not $spec.geometry) { throw "No built spec with a geometry hash for '$name'; build it first" }
        $approvals[$name] = [ordered]@{ geometry = $spec.geometry; by = $By; date = (Get-Date -Format 'yyyy-MM-dd') }
        Write-Host "Approved: $name ($($spec.geometry), by $By)"
    }
    $sorted = [ordered]@{}
    foreach ($key in ($approvals.Keys | Sort-Object)) { $sorted[$key] = $approvals[$key] }
    $sorted | ConvertTo-Json | Set-Content -LiteralPath $approvalsPath -Encoding UTF8
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
        $log = Join-Path $LogRoot 'verify-tests.log'
        $code = Invoke-Step 'Test.ps1' @('-Platform', 'EditMode') $log
        $line = Select-String -LiteralPath $log -Pattern '^Tests:' | Select-Object -First 1
        Write-Host ($(if ($line) { $line.Line } else { 'Tests: no result (Logs\verify-tests.log)' }))
        foreach ($f in @(Select-String -LiteralPath $log -Pattern 'FAILED:' -Context 0, 1 | Select-Object -First 8)) {
            Write-Host ('  ' + $f.Line.Trim() + ' :: ' + ($f.Context.PostContext -join ' ').Trim())
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
# Technical success is not approval: one line on what still waits for a review or for the user
$waiting = @($all | ForEach-Object { $s = Get-ApprovalState $_; if ($s -ne 'approved') { "$_ ($s)" } })
if ($waiting.Count) { Write-Host ("Approval: {0}/{1} approved; waiting: {2}" -f ($all.Count - $waiting.Count), $all.Count, ($waiting -join ', ')) }
else { Write-Host "Approval: all $($all.Count) approved" }
if ($failed.Count) { Write-Host ("FAILED: " + ($failed -join ', ')); exit 1 }
Write-Host 'All passed'
