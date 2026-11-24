# Flash CYT2BL3: SEGGER J-Link or CMSIS-DAP/DAPLink via OpenOCD.
#
#   .\flash.ps1                    auto-detect probe
#   .\flash.ps1 -Probe daplink     skip detection entirely (fastest)
#   .\flash.ps1 -Probe jlink       force J-Link
#   .\flash.ps1 -SkipVerify        don't read back the image
#
# Why not 'make program': the MTB recipe hardcodes interface/kitprog3.cfg and
# only accepts KitProg3 / JLink, so a generic CMSIS-DAP always fails there.
#
# Why the CMSIS-DAP path must reset first: a plain "halt + flash write_image
# erase" always dies with "SROM API execution failed" (double fault inside the
# CM0+ flash stub). 'traveo2 reset_halt sysresetreq' drops the SWD DP -- T2G
# powers down the debug domain on SYSRESETREQ -- but leaves the chip in a state
# where the erase algorithm works, and the next OpenOCD run reconnects.

param(
    [ValidateSet('auto', 'jlink', 'daplink')]
    [string]$Probe = 'auto',
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Continue'
$sw = [Diagnostics.Stopwatch]::StartNew()

$projRoot = Split-Path -Parent $PSScriptRoot

# Newest hex produced by the build
$cfgDir  = Join-Path $projRoot 'build\last_config'
$hexFile = Get-ChildItem $cfgDir -Filter '*.hex' -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $hexFile) { Write-Error "No hex in $cfgDir - build first"; exit 1 }
$hex = $hexFile.FullName

Write-Host "HEX : $hex"

# Stale-hex guard: sources newer than the image means the flash will not match.
$newerSrc = Get-ChildItem $projRoot -Recurse -Include '*.c', '*.h' -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -gt $hexFile.LastWriteTime -and
                           $_.FullName -notmatch '\\build\\' } |
            Select-Object -First 3
if ($newerSrc) {
    Write-Host 'WARNING: sources changed after this hex was built:' -ForegroundColor Yellow
    $newerSrc | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Yellow }
    Write-Host '         run Build first, or use "Build & Program".' -ForegroundColor Yellow
}

# Test-Path on known locations is ~165x faster than a recursive Get-ChildItem
# (2.15 s -> 0.013 s), which was the single biggest delay in this script.
function Find-JLinkExe {
    foreach ($p in @('D:\stm32_tools\jlink\JLink_V988\JLink.exe',
                     'C:\Program Files\SEGGER\JLink\JLink.exe',
                     'C:\Program Files (x86)\SEGGER\JLink\JLink.exe')) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

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
    $jlink = Find-JLinkExe
    $useJLink = $jlink -and (Test-JLinkProbe)
}

if ($useJLink) {
    # ---------- J-Link ----------
    Write-Host "Probe: J-Link ($Probe mode)"

    $cmd = Join-Path ([System.IO.Path]::GetTempPath()) 'mtb_program.jlink'
    @(
        'Connect'
        'exec EnableEraseAllFlashBanks'
        "LoadFile $($hex -replace '\\','/') 0 reset"
        'Reset'
        'Go'
        'Exit'
    ) | Set-Content -Path $cmd -Encoding ASCII

    & $jlink -AutoConnect 1 -ExitOnError 1 -NoGui 1 `
              -Device CYT2BL3CAS_M0 -If SWD -Speed 4000 `
              -CommandFile $cmd

    if ($LASTEXITCODE -ne 0) { Write-Error 'J-Link programming failed'; exit 1 }
    Write-Host ''
    Write-Host ('FLASH OK (J-Link) in {0:N1} s.' -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
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

# Step 1: reset so the CM0+ flash algorithm starts clean. OpenOCD spends ~23 s
# here retrying "cannot read IDR" (44 attempts) after the SYSRESETREQ has
# already closed the debug domain. The reset itself is instantaneous, so watch
# the output for that first "cannot read IDR" and kill the process. Measured
# 23.8 s -> 2.4 s.
#
# Start-Process joins -ArgumentList with spaces without quoting, so every
# argument containing a space must be quoted by hand (otherwise 'source [find
# interface/cmsis-dap.cfg]' is split and OpenOCD aborts with "Unexpected
# command line argument: [find").
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

# Step 2: write + verify. This session must run to completion -- killing it
# before "verified" would leave the image half programmed.
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

# Step 3: start the firmware. Must run to completion -- aborting this one too
# early leaves CM0+ stuck in the flash stub (observed PC in SRAM at 0x0800_xxxx).
& $ocd @common -c 'init' -c 'reset run' -c 'shutdown' 2>&1 | Out-Null

Write-Host ''
Write-Host ('FLASH OK (CMSIS-DAP) in {0:N1} s.' -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
