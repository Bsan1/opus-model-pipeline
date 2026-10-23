# Runs the Blender model generators in the background (no window opens): FBX + spec file + labelled contact sheet.
# Usage: powershell -ExecutionPolicy Bypass -File tools/Models.ps1 [-Only wheel] [-Checks] [-BlenderPath <blender.exe>]
# -Checks: runs the pipeline checks (tools/blender/checks/*.py, e.g. rigid body placement); without -Only
#          only the checks run, no models are generated.
#
# Generators: tools/blender/models/*.py; shared rules (1 unit = 1 m, axes, material names) in tools/blender/opus_model.py.
# Outputs: Assets/Opus/Resources/Models/<name>.fbx, Assets/Opus/ModelSpecs/<name>.json, Builds/Models/<name>_contact.png.
# -Preview: the structure only (validation, plan, construction gate, renders; no other gates, no baking, no FBX or spec):
#           Builds/Models/<name>_preview.png in seconds instead of minutes, for looking at a model before detailing it.
param([string]$Only, [switch]$Checks, [string]$BlenderPath, [switch]$Preview)
. (Join-Path $PSScriptRoot '_common.ps1')
Add-Type -AssemblyName System.Drawing

# Combines the views rendered by Blender and the reference crops on a single labelled page.
function New-ContactSheet([string]$Model, [switch]$Preview) {
    $folder = if ($Preview) { "${Model}_preview" } else { $Model }
    $dir = Join-Path $ProjectRoot "Builds\Models\$folder"
    $viewsPath = Join-Path $dir 'views.json'
    if (-not (Test-Path -LiteralPath $viewsPath)) { return $null }
    $views = @((Get-Content -LiteralPath $viewsPath -Raw -Encoding UTF8 | ConvertFrom-Json).views)
    $specPath = if ($Preview) { Join-Path $dir 'spec.json' } else { Join-Path $ProjectRoot "Assets\Opus\ModelSpecs\$Model.json" }
    $spec = Get-Content -LiteralPath $specPath -Raw -Encoding UTF8 | ConvertFrom-Json

    $tile = 640
    $cols = [Math]::Min(3, $views.Count)
    $rows = [Math]::Ceiling($views.Count / $cols)
    $header = 54
    # Material card: every slot's colour, finish and reason (what it really is, what shows in the video)
    $surfaces = @($spec.surfaces)
    $cardRow = 30
    $card = if ($surfaces.Count -gt 0) { 56 + $surfaces.Count * $cardRow } else { 0 }
    # Plan card: what every component does, what holds it, whether it moves, seen or guessed (Model.plan)
    $components = if ($spec.plan) { @($spec.plan.components) } else { @() }
    $planRow = 26
    $planCard = if ($components.Count -gt 0) { 96 + $components.Count * $planRow } else { 0 }
    $sheet = New-Object System.Drawing.Bitmap ($cols * $tile), ($rows * $tile + $header + $card + $planCard)
    $g = [System.Drawing.Graphics]::FromImage($sheet)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::FromArgb(243, 236, 223))
    $titleFont = New-Object System.Drawing.Font 'Segoe UI', 17, ([System.Drawing.FontStyle]::Bold)
    $labelFont = New-Object System.Drawing.Font 'Segoe UI', 13
    $ink = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(50, 46, 40))
    $paper = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(220, 243, 236, 223))
    $line = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(243, 236, 223)), 4

    $parts = ($spec.objects | ForEach-Object { '{0}: {1:N0} tris' -f $_.name, $_.triangles }) -join '   '
    $g.DrawString("$Model   $parts", $titleFont, $ink, 12, 12)
    for ($i = 0; $i -lt $views.Count; $i++) {
        $view = $views[$i]
        $x = ($i % $cols) * $tile
        $y = [Math]::Floor($i / $cols) * $tile + $header
        $image = $null
        if ($view.type -eq 'render') {
            $image = [System.Drawing.Image]::FromFile((Join-Path $dir $view.file))
            $g.DrawImage($image, (New-Object System.Drawing.Rectangle $x, $y, $tile, $tile))
        }
        elseif (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $view.path))) {
            # Reference frame missing (the public pipeline repository leaves out these crops of a copyrighted video)
            $g.FillRectangle((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(60, 58, 54))), $x, $y, $tile, $tile)
            $g.DrawString("not here: $($view.path)", $labelFont, $paper, $x + 16, $y + $tile / 2)
        }
        else {
            # Reference crop: fitted into the tile keeping the aspect ratio
            $image = [System.Drawing.Image]::FromFile((Join-Path $ProjectRoot $view.path))
            $c = $view.crop
            $scale = [Math]::Min($tile / $c[2], $tile / $c[3])
            $w = $c[2] * $scale
            $h = $c[3] * $scale
            $g.FillRectangle((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(60, 58, 54))), $x, $y, $tile, $tile)
            $target = New-Object System.Drawing.RectangleF ($x + ($tile - $w) / 2), ($y + ($tile - $h) / 2), $w, $h
            $source = New-Object System.Drawing.RectangleF $c[0], $c[1], $c[2], $c[3]
            $g.DrawImage($image, $target, $source, [System.Drawing.GraphicsUnit]::Pixel)
        }
        if ($image) { $image.Dispose() }
        $g.DrawRectangle($line, $x, $y, $tile, $tile)
        $size = $g.MeasureString($view.label, $labelFont)
        $g.FillRectangle($paper, $x + 10, $y + 10, $size.Width + 12, $size.Height + 6)
        $g.DrawString($view.label, $labelFont, $ink, $x + 16, $y + 13)
    }
    if ($card -gt 0) {
        $y = $rows * $tile + $header + 14
        $g.DrawString('Material card (the finish comes from the part''s real material and the video, not from the kind)', $titleFont, $ink, 12, $y)
        $y += 40
        $finishFont = New-Object System.Drawing.Font 'Segoe UI', 12, ([System.Drawing.FontStyle]::Bold)
        foreach ($surface in $surfaces) {
            $hex = $surface.name.Split('_')[1]
            if ($surface.name.StartsWith('Source_')) {
                # Textured source material: no single colour, the card shows its name
                $g.DrawString($hex, $finishFont, $ink, 14, $y + 2)
            }
            else {
                $swatch = [System.Drawing.ColorTranslator]::FromHtml('#' + $hex)
                $g.FillRectangle((New-Object System.Drawing.SolidBrush $swatch), 14, $y + 3, 34, 20)
            }
            $g.DrawRectangle((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(120, 110, 100)), 1), 14, $y + 3, 34, 20)
            $g.DrawString($surface.finish, $finishFont, $ink, 58, $y + 2)
            $g.DrawString($surface.note, $labelFont, $ink, 150, $y + 1)
            $y += $cardRow
        }
    }
    if ($planCard -gt 0) {
        $y = $rows * $tile + $header + $card + 14
        $g.DrawString("Plan: $($spec.plan.purpose)", $titleFont, $ink, 12, $y)
        $sources = ($spec.plan.sources | ForEach-Object { "$($_.kind): $($_.where)" }) -join '; '
        $g.DrawString("Sources: $sources   Held by: $($spec.plan.supports -join ', ')   Tier: $($spec.plan.tier)", $labelFont, $ink, 14, $y + 36)
        $y += 70
        $boldFont = New-Object System.Drawing.Font 'Segoe UI', 12, ([System.Drawing.FontStyle]::Bold)
        foreach ($c in $components) {
            $g.DrawString($c.name, $boldFont, $ink, 14, $y)
            $g.DrawString(('{0}, {1}, {2}' -f $c.role, $c.moves, $c.source), $labelFont, $ink, 230, $y)
            $g.DrawString(('{0}  -> {1}' -f $c.job, ($c.attaches -join ', ')), $labelFont, $ink, 470, $y)
            $y += $planRow
        }
    }
    $out = Join-Path $ProjectRoot "Builds\Models\${folder}$(if ($Preview) { '.png' } else { '_contact.png' })"
    $sheet.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $sheet.Dispose()
    return $out
}

$blender = Get-BlenderPath $BlenderPath

function Invoke-BlenderScript([string]$Script, [string]$Name) {
    $stdout = Join-Path $LogRoot "blender-$Name.log"
    $stderr = Join-Path $LogRoot "blender-$Name.err.log"
    $blenderArgs = @('-b', '--factory-startup', '--python-exit-code', '1', '--python', $Script)
    $argLine = ($blenderArgs | ForEach-Object { Format-Arg "$_" }) -join ' '
    $process = Start-Process -FilePath $blender -ArgumentList $argLine -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    foreach ($match in (Select-String -LiteralPath $stdout -Pattern '^\[Opus\]' -Encoding UTF8)) { Write-Host ('  ' + $match.Line) }
    if ($process.ExitCode -ne 0) {
        foreach ($text in (Get-Content -LiteralPath $stderr -Tail 40 -Encoding UTF8)) { Write-Host "  $text" }
        throw "Blender script failed: $Name (exit code $($process.ExitCode)); Logs\blender-$Name.log"
    }
}

if ($Checks) {
    foreach ($check in @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'blender\checks') -Filter '*.py' | Sort-Object Name)) {
        Write-Host "Check: $($check.BaseName) ..."
        $watch = [Diagnostics.Stopwatch]::StartNew()
        Invoke-BlenderScript $check.FullName "check-$($check.BaseName)"
        Write-Host ('Passed: {0} ({1:N0} s)' -f $check.BaseName, $watch.Elapsed.TotalSeconds)
    }
    if (-not $Only) { return }   # checks only; models with -Only or without -Checks
}

# wheel first: mower imports wheel.fbx
$generators = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'blender\models') -Filter '*.py' |
    Sort-Object @{ Expression = { $_.BaseName -ne 'wheel' } }, Name)
if ($Only) {
    $generators = @($generators | Where-Object { $_.BaseName -eq $Only })
    if ($generators.Count -eq 0) { throw "No generator: tools/blender/models/$Only.py" }
}

if ($Preview) { $env:OPUS_PREVIEW = '1' }   # read by opus_model.PREVIEW in the Blender process
foreach ($generator in $generators) {
    $name = $generator.BaseName
    Write-Host "Blender: $name$(if ($Preview) { ' (preview)' }) ..."
    $watch = [Diagnostics.Stopwatch]::StartNew()
    Invoke-BlenderScript $generator.FullName $(if ($Preview) { "$name-preview" } else { $name })
    $sheet = New-ContactSheet $name -Preview:$Preview
    Write-Host ('Done: {0} ({1:N0} s)' -f $name, $watch.Elapsed.TotalSeconds)
    if ($sheet) { Write-Host "  Contact sheet: $sheet" }
}
