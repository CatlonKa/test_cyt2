# Troubleshooting and sources

Contents:

- common failure modes
- middleware and PDL compatibility
- clock configuration and effective SMIF frequency
- troubleshooting checklist
- known-good reference workflow
- decision tree
- anti-patterns
- timeout after successful init — ordered checks
- protocol-state recovery before quad-mode detection
- sources

## Common failure modes

| Symptom | First thing to check |
| --- | --- |
| `SMIF0_HW` / `SMIF0_config` / `SMIF0_hal_config` undeclared at compile time | The SMIF peripheral is not enabled in the Device Configurator — these come from `cycfg_peripherals.h`, not from the QSPI Configurator. See [configurators.md §Device Configurator](./configurators.md#device-configurator--enable-the-smif-peripheral) |
| `smif_0_HW` / `SMIF_0_hal_config` generated instead, and no `_config` struct | The Device Configurator block was left unnamed. Have the user set the block name/alias to `SMIF0` |
| `smif0BlockConfig` / `smifBlockConfig` undeclared | No memory slot configured, so `cycfg_qspi_memslot.*` was never generated. See [configurators.md §QSPI Configurator](./configurators.md#qspi-configurator--configure-the-memory-slots). Common when a code example is offered for a board it ships no `templates/TARGET_<board>/` for |
| `fatal error: cyhal.h: No such file or directory` | An `mtb-hal-<device>` BSP (`mtb_hal.h` only) was paired with the legacy `serial-flash` library, whose `cy_serial_flash_qspi.h` includes `cyhal.h` and whose `init()` takes `cyhal_gpio_t` pins. That combination cannot build — switch to `serial-memory` |
| Setup/init returns an error | SMIF clock configured? `Cy_SMIF_Init` + `Cy_SMIF_Enable` called first (`serial-memory`)? |
| Reported memory size is 0 or wrong | Wrong block config symbol or wrong chip select for the slot |
| Reported size differs from the slot `Size` | Expected — the API reports the device capacity, not the configurator window |
| Write appears to succeed, read returns `0xFF` | Missing erase, or the write crossed into a sector erased afterwards |
| Setup succeeds and the size is right, but the first erase or write fails | Start with the effective SMIF clock path and generated clock assignment, then follow [Timeout after successful init — ordered checks](#timeout-after-successful-init--ordered-checks). Use [configurators.md](./configurators.md#device-configurator--validate-the-smif-clock-path-not-just-the-divider) for clock tracing and [board-memory-map.md](./board-memory-map.md#pin-routing) for routing checks |
| Write returns an error on flash | Inspect `WriteEnable` for that slot in `design.cyqspi`, but do not treat it as the only cause |
| XIP pointer reads garbage | Slot not `MemoryMapped`, wrong start address, or XIP not enabled |
| API reads/writes verify, but the XIP read is partly right (e.g. alternating correct bytes and `0xFF`) | The slot uses `Auto_detect_SFDP`. SFDP covers command-based access only; select the explicit memory part so the memory-mapped read command and dummy cycles are correct |
| Only one of the two flash devices on a B-H kit is reachable | Each device is its own slot and chip select. Configure a second slot on `QUAD_SPI_DATA_4_7` and set it up with the matching `MTB_SERIAL_MEMORY_CHIP_SELECT_<n>` |
| Reads are stale | Cache not invalidated for the SMIF region |
| Link errors mentioning both APIs | Both `serial-memory` and `serial-flash` installed |
| PSRAM data lost after reset | Expected — PSRAM is volatile; use flash for persistence |

## Middleware and PDL compatibility

`serial-memory` is fixed at `release-v2.0.0` for this SMIF flow. Do not upgrade it to fix a build
error; newer releases are not supported here. First confirm `deps/serial-memory.mtb` really
resolves to `release-v2.0.0` — see
[library-selection.md](./library-selection.md#pin-serial-memory-to-release-v200).

If the pinned release still does not build, compare the rest of the stack against the board
family's known-good reference project:

- the BSP and its `mtb-hal-<device>` asset
- `mtb-pdl-cat1`
- `core-lib`, `abstraction-rtos` (if used), and the other `deps/` / `deps/assetlocks.json` entries

Typical compatibility failure signs:

- missing SMIF driver types or enums
- `mtb_serial_memory_*` calls that do not match the `release-v2.0.0` header
- build errors in `serial-memory` caused by incompatible PDL symbols
- `fatal error: mtb_hal.h: No such file or directory` — the BSP uses `mtb-hal-cat1`; see
  [library-selection.md](./library-selection.md#decision-rules)

If these appear, stop and resolve version compatibility before debugging clocks, pins, or slot
settings.

## Clock configuration and effective SMIF frequency

Trace and calculate the effective SMIF clock with
[configurators.md §Validate the SMIF clock path](./configurators.md#device-configurator--validate-the-smif-clock-path-not-just-the-divider)
before using this section. This section records the one observed failure case and applies only
to an `S25HL512T` quad-SPI setup on `SMIF0`, or to a project with the same generated clock path
and lane topology.

- In that observed reference path the generated clock comes through `HFCLK6`, and the effective
  SMIF clock had to stay below **160 MHz** for erase, write, and read to pass. This is an
  observed path-specific result, not a published chip-wide limit.
- `HFCLK6` divider `1` produced the failing frequency; divider `2` reduced the effective SMIF
  clock enough for runtime access to pass. Initialization still succeeded at the failing
  frequency.
- The real constraint is the final effective SMIF clock frequency, not the raw divider value. If
  the project does not match that generated path and topology, do not reuse those divider values.

The `S25HL512T` datasheet is authoritative for supported SPI / quad-SPI protocols, reset
behaviour and flash semantics, but it does not define the MCU `HFCLK` or peripheral clock
configuration. For the MCU clock tree, the authoritative sources are the project's Device
Configurator output, the generated clock files, the installed PDL headers and a known-working
reference project.

Do not add a requirement to validate `D4`-`D7` for this quad-SPI configuration. The
failure case was clock-related, not a problem with the unused upper data lanes.

## Troubleshooting checklist

Use this checklist when a project builds but SMIF behavior is still wrong on hardware:

1. confirm `serial-memory` is `release-v2.0.0` and the PDL / BSP set is compatible
2. confirm the SMIF peripheral exists in `design.modus` and in `cycfg_peripherals.*`
3. confirm the QSPI slot exists in `design.cyqspi` and in `cycfg_qspi_memslot.*`
4. confirm `cycfg_routing.h` matches the intended pins and topology
5. confirm `cycfg_system.*` and `cycfg_clocks.*` match the intended clock source path,
   dividers, and frequency
6. confirm the initialization code uses the generated SMIF symbols and the installed library API
7. if the generated files look correct but hardware behavior still disagrees, print runtime clock
  diagnostics and compare them with the generated files
8. run behavior-scoped flash validation: erase, raw read `0xFF`, raw write, raw read-back,
   direct buffer compare

## Known-good reference workflow

When a local reference project is available, compare generated outputs first, not just source
files.

Compare all of these against the working project:

- `cycfg_peripherals.*`
- `cycfg_qspi_memslot.*`
- `cycfg_routing.h`
- `cycfg_system.*`
- middleware versions
- actual data-line mode and slot settings
- runtime UART diagnostics, if available

A board-specific local reference project is usually more reliable than generic setup steps.

## Decision tree

### Build fails because of missing or incompatible `serial-memory` APIs

- inspect `../mtb_shared/serial-memory/release-v2.0.0/include/mtb_serial_memory.h`
- confirm `deps/serial-memory.mtb` resolves to `release-v2.0.0`
- compare the BSP, HAL and PDL versions with the board family's working reference project
- inspect PDL compatibility before changing any SMIF slot or clock setting

### SMIF init fails

- inspect `cycfg_peripherals.*` to confirm the SMIF block exists and uses the intended instance
- inspect `cycfg_system.*` to confirm the SMIF HF clock path and divider are valid
- inspect init code to confirm it uses the generated SMIF config and clock handle

### Erase fails

- inspect the SMIF clock path and effective frequency first
- inspect `WriteEnable`, chip select, slot, and data-line mode in `cycfg_qspi_memslot.*`, matching them against the proven project/reference configuration
- inspect routing and protocol recovery state for the part

### Erase succeeds but read-back is not `0xFF`

- confirm the read path independently of the erase path
- inspect address width, read command, data width, and routing
- compare the same raw read on a known-good reference project

### Erase and write succeed but first bytes are corrupted on read-back

- inspect read command width and dummy-cycle related settings in `cycfg_qspi_memslot.*`
- inspect clock frequency and compare it with the reference project
- inspect whether XIP and explicit read mode behave differently

### Memory-mapped mode works differently from explicit read/write mode

- inspect whether the slot still uses `Auto_detect_SFDP`
- inspect memory-mapped flags, base address, command selection, and dummy-cycle related fields
- compare the configured part selection with the reference project

### Reference project works but new project fails

- compare generated files, not only source code
- compare clock-tree outputs and routing
- compare middleware versions and installed PDLs
- compare slot settings, data-line mode, chip select, and runtime diagnostics
- keep comparing until one configuration surface differs, then fix that exact surface

## Anti-patterns

- assuming generated aliases mean the configuration is correct
- assuming a successful build means SMIF is configured correctly
- assuming successful erase or write proves full correctness
- editing `GeneratedSource/` manually
- overriding clock or pin routing in application code instead of fixing configurator settings
- copying every signal from a reference project without checking whether that signal matters for
  the current flash mode

## Timeout after successful init — ordered checks

When SMIF initialization succeeds but erase or write times out with
`CY_SMIF_EXCEED_TIMEOUT` (`0x00B20002`), check in this order:

| Symptom | Check in this order | Why this order matters |
| --- | --- | --- |
| SMIF initialization succeeds, but erase/write times out with `CY_SMIF_EXCEED_TIMEOUT` (`0x00B20002`) | 1. active SMIF instance and clock handle<br>2. SMIF clock source<br>3. active `HFCLK` and its divider<br>4. peripheral clock divider<br>5. generated SMIF HAL clock assignment<br>6. flash reset and quad-enable state<br>7. chip-select and data-select configuration | The same timeout can be caused by more than one layer. On the scoped `S25HL512T` quad-SPI reference path, an incorrect clock divider can cause this failure even though initialization succeeds, so do not jump straight to RWDS or DDR wiring assumptions. |

## Protocol-state recovery before quad-mode detection

If the flash device may have retained an unexpected protocol state, recover it before deciding
that the board or slot configuration is wrong.

- Issue the flash mode-bit reset and software reset before quad-mode detection.
- Retry quad-mode enable a limited number of times rather than looping indefinitely.
- Report the raw SMIF / PDL status from each attempt so the user can distinguish a clock failure
  from a protocol-state failure.

The detailed example-derived recovery sequence is documented in
[example-s25hl512t.md](./example-s25hl512t.md) for the `S25HL512T` quad-SPI case.

## Sources

The API shapes, dependency names and flash-vs-PSRAM differences were taken from these Infineon
code examples and libraries. Use the Library column to tell at a glance which API an example
demonstrates — the example names do not say.

| Code example | Library | API prefix | Memory | Supported kits |
| --- | --- | --- | --- | --- |
| `Infineon/mtb-example-ce241383-smif-flash-readwrite` | `serial-memory` (current) | `mtb_serial_memory_*` | external NOR flash | KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-4M_LITE, KIT_T2G-B-H_LITE, KIT_T2G_B-H-16M_LITE |
| `Infineon/mtb-example-ce241382-smif-psram-readwrite` | `serial-memory` (current) | `mtb_serial_memory_*` | external PSRAM, no erase step | C-2D kits |
| `Infineon/mtb-t2g-example-smif-qspi-flash-read-write` | `serial-flash` (legacy) | `cy_serial_flash_qspi_*` | QSPI NOR flash | KIT_T2G-B-H_LITE, KIT_T2G-B-H_EVK only |

Library repositories: `Infineon/serial-memory`, `Infineon/serial-flash`.

Board and API behaviour in these files was checked against the libraries' own headers and against
builds and hardware runs on KIT_T2G-B-H_LITE, KIT_T2G_C-2D-4M_LITE, KIT_T2G_C-2D-6M_LITE and
KIT_T2G_B-H-16M_LITE. The `S25HL512T` divider and timeout guidance specifically comes from the B-H
family quad-SPI topology and should only be reused directly when the project matches that
generated SMIF path.

If the user's project disagrees with any of the above, the project wins — re-read its headers and
generated configuration and say so.
