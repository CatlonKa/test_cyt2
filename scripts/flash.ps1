# Flash / erase CYT2BL3 over SWD.
#
#   .\flash.ps1                  flash newest hex
#   .\flash.ps1 -Probe jlink     force probe  (auto | jlink | daplink)
#   .\flash.ps1 -SkipVerify      skip read-back
#   .\flash.ps1 -Erase Main      erase main flash        (0x10000000)
#   .\flash.ps1 -Erase All       erase main + work flash (0x10000000, 0x14000000)
#
# Probe defaults to "cyt2.defaultProbe" in .vscode/settings.json.
#
# Not "make program": the recipe hardcodes interface/kitprog3.cfg and only
# accepts KitProg3 / J-Link, so a generic CMSIS-DAP always fails there.

param(
    [ValidateSet('auto', 'jlink', 'daplink')]
    [string]$Probe,
    [ValidateSet('None', 'Main', 'All')]
    [string]$Erase = 'None',
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Continue'
$sw = [Diagnostics.Stopwatch]::StartNew()

$projRoot = Split-Path -Parent $PSScriptRoot

# -Probe > settings.json > auto
if (-not $Probe) {
    $Probe = 'auto'
    $settingsPath = Join-Path $projRoot '.vscode\settings.json'
    if (Test-Path $settingsPath) {
        # Explicit UTF8: PS 5.1 defaults to ANSI and mangles non-ASCII comments.
        $raw = [IO.File]::ReadAllText($settingsPath, [Text.Encoding]::UTF8)
        $clean = ($raw -replace '(?m)^\s*//.*$', '') -replace '/\*[\s\S]*?\*/', ''
        try {
            $pref = ($clean | ConvertFrom-Json).'cyt2.defaultProbe'
            if ($pref -in @('auto', 'jlink', 'daplink')) { $Probe = $pref }
        } catch { }
    }
}

# ---------- newest hex ----------
if ($Erase -eq 'None') {
    $cfgDir = Join-Path $projRoot 'build\last_config'
    $hexFile = Get-ChildItem $cfgDir -Filter '*.hex' -ErrorAction SilentlyContinue |
               Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $hexFile) { Write-Error "No hex in $cfgDir - build first"; exit 1 }
    $hex = $hexFile.FullName

    Write-Host "HEX : $hex"

    # Sources newer than the image means a stale flash.
    $newerSrc = Get-ChildItem $projRoot -Recurse -Include '*.c', '*.h' -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt $hexFile.LastWriteTime -and
                               $_.FullName -notmatch '\\build\\' } |
                Select-Object -First 3
    if ($newerSrc) {
        Write-Host 'WARNING: sources changed after this hex was built:' -ForegroundColor Yellow
        $newerSrc | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Yellow }
        Write-Host '         run Build first, or use "Compile & Flash".' -ForegroundColor Yellow
    }
}

# Fixed paths only: a recursive search cost 2 s per run.
function Find-JLinkExe {
    foreach ($p in @('D:\stm32_tools\jlink\JLink_V988\JLink.exe',
                     'C:\Program Files\SEGGER\JLink\JLink.exe',
                     'C:\Program Files (x86)\SEGGER\JLink\JLink.exe')) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# PnP enumeration costs ~1.1 s, so only auto mode calls this.
function Test-JLinkProbe {
    $null -ne (Get-CimInstance Win32_PnPEntity -Filter "DeviceID LIKE 'USB\\VID_1366%'" `
                    -ErrorAction SilentlyContinue)
}

$jlink = $null
$useJLink = $false
if ($Probe -eq 'jlink') {
    $jlink = Find-JLinkExe
    if (-not $jlink) { Write-Error 'JLink.exe not found'; exit 1 }
    $useJLink = $true
} elseif ($Probe -eq 'auto') {
    $swDetect = [Diagnostics.Stopwatch]::StartNew()
    $jlink = Find-JLinkExe
    $useJLink = $jlink -and (Test-JLinkProbe)
    Write-Host ('Probe: auto-detect took {0:N1} s (pin cyt2.defaultProbe in' -f $swDetect.Elapsed.TotalSeconds)
    Write-Host '       .vscode/settings.json to skip this)'
}

if ($useJLink) {
    # ---------- J-Link ----------
    Write-Host "Probe: J-Link ($Probe mode)"

    $cmd = Join-Path ([System.IO.Path]::GetTempPath()) 'mtb_program.jlink'
    if ($Erase -ne 'None') {
        # 'Erase' erases every non-protected bank.
        @(
            'Connect'
            'exec EnableEraseAllFlashBanks'
            'Erase'
            'Exit'
        ) | Set-Content -Path $cmd -Encoding ASCII
    } else {
        @(
            'Connect'
            'exec EnableEraseAllFlashBanks'
            "LoadFile $($hex -replace '\\','/') 0 reset"
            'Reset'
            'Go'
            'Exit'
        ) | Set-Content -Path $cmd -Encoding ASCII
    }

    & $jlink -AutoConnect 1 -ExitOnError 1 -NoGui 1 `
              -Device CYT2BL3CAS_M0 -If SWD -Speed 4000 `
              -CommandFile $cmd

    if ($LASTEXITCODE -ne 0) {
        Write-Error $(if ($Erase -ne 'None') { 'J-Link erase failed' } else { 'J-Link programming failed' })
        exit 1
    }
    Write-Host ''
    if ($Erase -ne 'None') {
        Write-Host ('ERASE OK (J-Link, {0}) in {1:N1} s.' -f $Erase, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    } else {
        Write-Host ('FLASH OK (J-Link) in {0:N1} s.' -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    }
    exit 0
}

# ---------- CMSIS-DAP / DAPLink ----------
Write-Host "Probe: CMSIS-DAP ($Probe mode)"

$ocdRoot = 'D:\Infineon\Tools\ModusToolboxProgtools-2.0\openocd'
if (-not (Test-Path (Join-Path $ocdRoot 'bin\openocd.exe'))) {
    $ocdRoot = $null
    foreach ($r in @('D:\Infineon\Tools', 'C:\Infineon\Tools')) {
        if (-not (Test-Path $r)) { continue }
        $dir = Get-ChildItem $r -Directory -Filter 'ModusToolboxProgtools-*' -ErrorAction SilentlyContinue |
               Sort-Object Name -Descending |
               ForEach-Object { Join-Path $_.FullName 'openocd' } |
               Where-Object { Test-Path (Join-Path $_ 'bin\openocd.exe') } |
               Select-Object -First 1
        if ($dir) { $ocdRoot = $dir; break }
    }
}
if (-not $ocdRoot) { Write-Error 'OpenOCD not found'; exit 1 }
$ocd     = Join-Path $ocdRoot 'bin\openocd.exe'
$scripts = Join-Path $ocdRoot 'scripts'

$common = @(
    '-s', $scripts,
    '-c', 'source [find interface/cmsis-dap.cfg]',
    '-c', 'transport select swd',
    '-c', 'source [find target/traveo2_be_4m.cfg]',
    '-c', 'adapter speed 1000'
)
$hexFwd = $hex -replace '\\', '/'

# Step 1: reset before the write. A bare "halt + flash write_image erase" always
# fails with "SROM API execution failed" (double fault in the CM0+ flash stub).
# SYSRESETREQ closes the debug domain, so OpenOCD retries "cannot read IDR" for
# ~23 s; the reset itself is instant, so kill the process at the first such line.
#
# Start-Process does not quote -ArgumentList, so args containing spaces must be
# quoted by hand or 'source [find ...]' is split ("Unexpected command line
# argument: [find").
function Quote-Args([string[]]$a) {
    return ($a | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } })
}

function Invoke-ResetAndAbort {
    $out = Join-Path ([System.IO.Path]::GetTempPath()) 'mtb_reset.out'
    $err = Join-Path ([System.IO.Path]::GetTempPath()) 'mtb_reset.err'
    Remove-Item $out, $err -Force -ErrorAction SilentlyContinue

    $swReset = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $ocd -NoNewWindow -PassThru `
         -ArgumentList (Quote-Args (@($common) + @('-c', 'init', '-c', 'traveo2 reset_halt sysresetreq', '-c', 'shutdown'))) `
         -RedirectStandardOutput $out -RedirectStandardError $err

    while ($swReset.Elapsed.TotalSeconds -lt 15) {
        Start-Sleep -Milliseconds 60
        if ($p.HasExited) { break }
        $e = if (Test-Path $err) { Get-Content $err -Raw -ErrorAction SilentlyContinue } else { '' }
        $o = if (Test-Path $out) { Get-Content $out -Raw -ErrorAction SilentlyContinue } else { '' }
        if ($e -match 'cannot read IDR' -or $o -match 'cannot read IDR') { break }
    }
    if (-not $p.HasExited) { try { $p.Kill() } catch { }; try { $p.WaitForExit() } catch { } }
    Remove-Item $out, $err -Force -ErrorAction SilentlyContinue
}

Invoke-ResetAndAbort
Start-Sleep -Milliseconds 500

# ---------- erase only ----------
if ($Erase -ne 'None') {
    # Erase     = internal flash only
    # Erase All = internal + external (QSPI/SMIF); this board has none
    # super flash / eFuse are never erased: they hold TOC and lock settings.
    if ($Erase -eq 'All') {
        $cyqspi = Join-Path $projRoot 'bsps\TARGET_CYT2BL3\config\design.cyqspi'
        if (-not (Test-Path $cyqspi)) {
            Write-Host '  note: no design.cyqspi, so "Erase All" == main + work flash'
        } else {
            Write-Host '  WARNING: external QSPI not erased by this script' -ForegroundColor Yellow
        }
    }

    # bank 0 = main (0x10000000), bank 1 = work (0x14000000)
    $banks = if ($Erase -eq 'All') { @(0, 1) } else { @(0) }
    $ok = $true
    foreach ($b in $banks) {
        $name = if ($b -eq 0) { 'main' } else { 'work' }
        Write-Host "  erasing $name flash (bank $b) ..."
        $t = (& $ocd @common -c 'init' -c 'targets traveo2_be_4m.cpu.cm0' -c 'halt' `
                           -c "traveo2 mass_erase $b" -c 'shutdown' 2>&1 | Out-String)
        if ($t -match 'SROM API execution failed|timed out') {
            Write-Host $t
            $ok = $false
            break
        }
    }
    if (-not $ok) {
        Write-Host ''
        Write-Host 'Erase algorithm crashed. Power-cycle the board and retry.' -ForegroundColor Yellow
        Write-Error 'erase failed'
        exit 1
    }
    Write-Host ''
    Write-Host ('ERASE OK (CMSIS-DAP, {0}) in {1:N1} s.' -f $Erase, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    exit 0
}

# Step 2: write + verify. Must run to completion; killing it early leaves the
# image half programmed.
$cmds = @('init', 'targets traveo2_be_4m.cpu.cm0', 'halt', "flash write_image erase $hexFwd")
if (-not $SkipVerify) { $cmds += "verify_image $hexFwd" }
$cmds += @('shutdown')
$ocdArgs = @()
foreach ($c in $cmds) { $ocdArgs += '-c'; $ocdArgs += $c }

$text = (& $ocd @common @ocdArgs 2>&1 | Out-String)

if ($text -notmatch 'wrote \d+ bytes') {
    Write-Host $text
    if ($text -match 'SROM API execution failed|lockup|timed out while waiting') {
        Write-Host ''
        Write-Host 'Flash algorithm crashed. Power-cycle the board and retry.' -ForegroundColor Yellow
    }
    Write-Error 'flash write failed'
    exit 1
}
Write-Host '  ' ([regex]::Match($text, 'wrote \d+ bytes[^\r\n]*').Value).Trim()

if (-not $SkipVerify) {
    if ($text -notmatch 'verified \d+ bytes') {
        Write-Host $text
        Write-Error 'verify failed'
        exit 1
    }
    Write-Host '  ' ([regex]::Match($text, 'verified \d+ bytes[^\r\n]*').Value).Trim()
}

# Step 3: start the firmware. Must run to completion; aborting it leaves CM0+
# stuck in the flash stub (PC in SRAM 0x0800_xxxx).
& $ocd @common -c 'init' -c 'reset run' -c 'shutdown' 2>&1 | Out-Null

Write-Host ''
Write-Host ('FLASH OK (CMSIS-DAP) in {0:N1} s.' -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
