# Flash CYT2BL3: prefers SEGGER J-Link, falls back to CMSIS-DAP + OpenOCD.
#
# Why not 'make program':
#   The MTB recipe hardcodes interface/kitprog3.cfg and only supports
#   KitProg3 / JLink. A generic CMSIS-DAP therefore never works through it.
#
# Why the CMSIS-DAP path must reset first:
#   A plain "halt + flash write_image erase" always fails on this device with
#   "SROM API execution failed" (double fault inside the CM0+ flash stub).
#   The reset below ('traveo2 reset_halt sysresetreq') drops the SWD DP --
#   TRAVEO T2G powers down the debug domain on SYSRESETREQ -- but that is fine:
#   the chip ends up in a state where the sector-erase algorithm works, and the
#   next OpenOCD invocation reconnects. Verified 6/6 on 2026-11-23.

$ErrorActionPreference = 'Continue'

$projRoot = Split-Path -Parent $PSScriptRoot

# Newest hex produced by the build
$cfgDir  = Join-Path $projRoot 'build\last_config'
$hexFile = Get-ChildItem $cfgDir -Filter '*.hex' -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $hexFile) { Write-Error "No hex in $cfgDir - build first"; exit 1 }
$hex = $hexFile.FullName

function Test-JLinkProbe {
    $dev = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
           Where-Object { $_.InstanceId -match 'VID_1366' }
    return [bool]$dev
}

function Find-JLinkExe {
    $cands = @()
    $cands += Get-ChildItem 'D:\stm32_tools\jlink', 'C:\Program Files\SEGGER', 'C:\Program Files (x86)\SEGGER' `
        -Recurse -Depth 2 -Filter 'JLink.exe' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    return $cands | Select-Object -First 1
}

$jlink = Find-JLinkExe
$useJLink = $jlink -and (Test-JLinkProbe)

Write-Host "HEX : $hex"

if ($useJLink) {
    # ---------- J-Link ----------
    Write-Host "Probe: J-Link ($jlink)"
    Write-Host ''
    Write-Host '--- J-Link program ---'

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
    Write-Host 'FLASH OK (J-Link).' -ForegroundColor Green
    exit 0
}

# ---------- CMSIS-DAP fallback ----------
Write-Host 'Probe: CMSIS-DAP (no J-Link detected)'
if ($jlink) { Write-Host 'Note: JLink.exe found but no J-Link probe enumerated.' -ForegroundColor Yellow }
Write-Host ''

$ocd = $null; $scripts = $null
foreach ($r in @('D:\Infineon\Tools', 'C:\Infineon\Tools')) {
    if (-not (Test-Path $r)) { continue }
    $dir = Get-ChildItem $r -Directory -Filter 'ModusToolboxProgtools-*' -ErrorAction SilentlyContinue |
           Sort-Object Name -Descending |
           ForEach-Object { Join-Path $_.FullName 'openocd' } |
           Where-Object { Test-Path (Join-Path $_ 'bin\openocd.exe') } |
           Select-Object -First 1
    if ($dir) { $ocd = Join-Path $dir 'bin\openocd.exe'; $scripts = Join-Path $dir 'scripts'; break }
}
if (-not $ocd) { Write-Error 'OpenOCD not found'; exit 1 }

$common = @(
    '-s', $scripts,
    '-c', 'source [find interface/cmsis-dap.cfg]',
    '-c', 'transport select swd',
    '-c', 'source [find target/traveo2_be_4m.cfg]',
    '-c', 'adapter speed 1000'
)
$hexFwd = $hex -replace '\\', '/'

# Verified working recipe (6/6 passes on 2026-11-23):
#   1) 'traveo2 reset_halt sysresetreq'  -- resets the chip so the CM0+ flash
#      algorithm runs in a clean state. The SWD DP is dropped by this reset,
#      which is expected; the following invocation reconnects.
#   2) halt + 'flash write_image erase'  -- sector erase now succeeds.
# Without step 1 the algorithm always dies with "SROM API execution failed"
# (double fault inside the CM0+ flash stub), regardless of clock speed.
Write-Host '--- reset target (SYSRESETREQ; the DP drop is expected) ---'
& $ocd @common -c 'init' -c 'traveo2 reset_halt sysresetreq' -c 'shutdown' 2>&1 | Out-Null
Start-Sleep -Seconds 2

Write-Host '--- write flash ---'
$text = (& $ocd @common -c 'init' -c 'targets traveo2_be_4m.cpu.cm0' -c 'halt' `
         -c "flash write_image erase $hexFwd" -c 'shutdown' 2>&1 | Out-String)
if ($text -notmatch 'wrote \d+ bytes') {
    Write-Host $text
    if ($text -match 'SROM API execution failed|lockup|timed out while waiting') {
        Write-Host ''
        Write-Host 'Retry once; if it keeps failing, connect J-Link.' -ForegroundColor Yellow
    }
    Write-Error 'flash write failed'
    exit 1
}
([regex]::Match($text, 'wrote \d+ bytes[^\r\n]*').Value)

Write-Host '--- verify ---'
$text = (& $ocd @common -c 'init' -c 'targets traveo2_be_4m.cpu.cm0' -c 'halt' `
         -c "verify_image $hexFwd" -c 'shutdown' 2>&1 | Out-String)
if ($text -notmatch 'verified \d+ bytes') { Write-Host $text; Write-Error 'verify failed'; exit 1 }
([regex]::Match($text, 'verified \d+ bytes[^\r\n]*').Value)

Write-Host '--- start firmware ---'
& $ocd @common -c 'init' -c 'reset run' -c 'shutdown' 2>&1 | Out-Null

Write-Host ''
Write-Host 'FLASH OK. Firmware restarted (power-cycle if it does not run).' -ForegroundColor Green
