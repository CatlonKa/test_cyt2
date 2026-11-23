# External memory parts fitted on TRAVEO T2G kits

Contents:

- at-a-glance part table
- supported communication modes by chip
- erase-size behaviour
- PSRAM behaviour
- Semper flash behaviour
- sources

Properties of the memory chip, as opposed to the board wiring (which is in
[board-memory-map.md](./board-memory-map.md)). Read this when you need to know what interface a
part supports, how big its erase unit is, whether it needs the RWDS strobe, or why a part behaves
in a way the SMIF configuration alone does not explain — and when the user's board is not in the
board table, so the part number is the only thing you have to go on.

The QSPI Configurator's own part library and the project's `design.cyqspi` are authoritative.
This file exists to let you sanity-check a slot and to explain chip behaviour; it is not a
substitute for reading the configuration. Runtime failure signatures and debug ordering belong in
[troubleshooting.md](./troubleshooting.md).

## At a glance

| Part | Type | Interface | Density | Erase | Needs RWDS / DS routed | Seen on |
| --- | --- | --- | --- | --- | --- | --- |
| S25HL512T | Semper NOR flash | SPI / dual / quad, SDR + `1S-4D-4D`, `4S-4D-4D` | 512 Mb (64 MB) | yes | only if a DDR protocol is selected | KIT_T2G-B-H_LITE (x2), KIT_T2G_B-H-16M_LITE (x2), KIT_T2G-B-H_EVK |
| S26HL512T | Semper NOR flash, HyperBus, 3.0 V | HyperBus (x8 DDR) or legacy x1 SPI | 512 Mb (64 MB) | yes | yes in HyperBus mode (`DS`) | KIT_T2G_C-2D-4M_LITE |
| S28HS512T | Semper NOR flash, Octal, 1.8 V | Octal DDR (xSPI) | 512 Mb (64 MB) | yes | yes | KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-6M-DDR_LITE |
| S27KL0642 | HyperRAM PSRAM, 3.0 V | HyperBus, x8 DDR | 64 Mb (8 MB) | no — never erase | yes (`RWDS`) | KIT_T2G_C-2D-4M_LITE |
| S27KS0642 | HyperRAM PSRAM, 1.8 V | HyperBus, x8 DDR | 64 Mb (8 MB) | no — never erase | yes (`RWDS`) | KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-6M-DDR_LITE |

Reading the part number:

- `S25HL*` / `S26HL*` / `S28HS*` — Semper NOR flash. `S25`/`S26` families are 3.0 V (`HL`),
  `S28`/`S26HS` are 1.8 V (`HS`). The `HL` vs `HS` pair in a family is the same die at a different
  supply — do not treat them as interchangeable in the configurator, the I/O voltage differs.
- `S27K*` — HyperRAM PSRAM. `S27KL` is 3.0 V, `S27KS` is 1.8 V.
- A part whose interface is HyperBus or Octal DDR always needs the bidirectional strobe
  (`RWDS` on PSRAM, `DS` on Semper flash) routed *and* given a digital drive mode. Leaving it
  `CY_GPIO_DM_ANALOG` fails identically to not routing it — see
  [troubleshooting.md](./troubleshooting.md).

## Supported communication modes by chip

Use this section when the user asks what communication mode a fitted part supports, or when the
QSPI / SMIF configurator choice is unclear.

- **`S25HL512T`.** Supports legacy SPI, dual SPI, and quad SPI at 3.0 V I/O. The Infineon
  S25HL512T documentation lists `1S-1S-1S`, `1S-2S-2S`, `1S-1S-4S`, `1S-4S-4S`, `1S-4D-4D`, `4S-4S-4S`, and
  `4S-4D-4D`. The scoped reference path in this skill uses the quad-SPI configuration, not
  HyperBus or octal mode. The S25HL512T quick-start material confirms the supported protocols, but
  it does not state a max clock rate; take the final frequency limit from the exact S25HL512T
  datasheet and the configurator part definition, not from analogy with other Semper families.
- **`S26HL512T` / `S26HS*`.** Supports HYPERBUS x8 DDR and legacy x1 SPI. It is not the same kind
  of quad-SPI flash as `S25HL512T`. The HYPERBUS path uses `DQ[7:0]`, `CS#`, clock, and the flash
  data strobe `DS`. The Semper HYPERBUS family also supports boot in either legacy SPI x1 or
  HYPERBUS x8, so do not assume the active mode from the part number alone. From the Semper
  HYPERBUS flash datasheet: HYPERBUS read DDR runs up to **200 MHz** on HS-T parts and up to
  **166 MHz** on HL-T parts; legacy x1 SPI fast read uses up to **166 MHz** clock, while plain SPI
  read is listed at **50 MHz**.
- **`S28HS512T`.** Use it as an Octal DDR xSPI flash part. It requires the full 8-bit data path
  and strobe routing. Keep the exact lane and timing configuration aligned with the configurator's
  explicit part definition.
- **`S27KL0642` / `S27KS0642`.** HyperRAM PSRAM with a HYPERBUS x8 DDR interface. The device uses
  `DQ[7:0]`, `CS#`, `RESET#`, and bidirectional `RWDS`. `RWDS` is not optional for working DDR
  access: it indicates added latency during command/address, acts as the read strobe during reads,
  and acts as the write mask during writes. The HyperRAM datasheet also allows either a
  single-ended clock or an optional differential clock pair. Per the same datasheet,
  both the 1.8 V and 3.0 V variants are rated for **200 MHz maximum clock**, with up to
  **400 MBps** data throughput.

For HyperBus parts, read and write traffic is burst-oriented. The HyperRAM datasheet calls
out linear, wrapped, and hybrid bursts; the Semper HYPERBUS flash datasheet calls out linear,
wrapped, and hybrid burst reads. Keep those behaviors in mind when comparing a working reference
project against a failing one.

## Why erase size is not a constant

Semper flash parts are configurable between a uniform 256 KB sector layout and hybrid
layouts where thirty-two 4 KB parameter sectors sit at the top, the bottom, or split between both,
with 256 KB sectors elsewhere. The layout is a device configuration, not a board property, so two
kits carrying the same 512 Mb part class can report different erase sizes at address 0 —
262144 bytes on KIT_T2G_C-2D-4M_LITE versus 4096 bytes on KIT_T2G_C-2D-6M_LITE.

Consequences for generated code:

- Always call `mtb_serial_memory_get_erase_size()` for the specific address being erased.
  Never hardcode a sector size and never reuse one read at a different address.
- An erase always affects the whole sector containing the address. Erasing "4 KB" at an address
  that happens to sit in a 256 KB region destroys 256 KB.
- PSRAM has no sectors and no erase. Calling an erase API on a PSRAM slot is always a bug.

## PSRAM (HyperRAM) behaviour relevant to generated code

These come from the device itself and are not visible in the SMIF configuration:

- **Volatile.** Contents are lost on power down. This is the intended difference from flash, and
  it is worth verifying in the Step 6 verification checklist in
  [code-patterns.md](./code-patterns.md#verification-checklist) rather than treating as a fault.
- **Self-refreshing DRAM.** The controller hides refresh, but refresh cannot happen while a
  transaction is in progress, so a single burst must not hold chip select low longer than `tCSM`
  (4 µs at 85 °C, **1 µs at 125 °C**). Very long single transfers at high temperature can starve
  refresh and corrupt data. Split large copies.
- **Variable initial latency.** The device raises RWDS during the command phase to demand an extra
  latency period when a refresh is pending. The default configuration is fixed (always 2x) latency,
  which is deterministic but slower. This is a device-register setting, not a configurator setting.
- **Deep Power Down loses the array.** Entering DPD stops refresh; data is gone on exit. Hybrid
  Sleep retains data. A hardware reset or POR also halts refresh — assume PSRAM contents are
  invalid after reset and reload them.
- **Density from the ID register.** `ID0` for the 64 Mb parts reads `0x0C81`: 13 row address bits
  and 9 column address bits → 4 Mwords → **8 MB**. This is why
  `mtb_serial_memory_get_size()` reports 8388608 for the PSRAM while the configurator slot `Size`
  may be something much smaller. That mismatch is expected and is not an error.

## Semper flash behaviour relevant to generated code

- **On-chip ECC.** An 8-bit ECC is computed per 16-byte data unit at program time. Programming the
  same 16-byte unit more than once without an intervening erase either disables ECC for that unit
  or, if 2-bit detection is enabled, fails with a program error. So byte-at-a-time patching of an
  already-programmed region is not safe — erase and rewrite the unit.
- **Erased state is `0xFF`.** Programming only clears bits 1 → 0; only an erase sets them back.
  A write that "did nothing" is usually a write into a region that was never erased.
- **Endurance is partitioned.** Semper parts can be configured with high-endurance versus
  long-retention regions, and this configuration is one-time on some devices. Do not generate code
  that reconfigures endurance partitioning as a side effect of a storage request.
- **Two devices still mean two chip selects.** `KIT_T2G-B-H_LITE` and
  `KIT_T2G_B-H-16M_LITE` fit two `S25HL512T` parts, so that is 2 x 64 MB behind two selects,
  not one 128 MB device — each needs its own slot and its own
  `MTB_SERIAL_MEMORY_CHIP_SELECT_<n>`. `KIT_T2G-B-H_EVK` fits one flash device, so it does not
  use the second-select rule unless a different custom design adds another chip.
- **`Auto_detect_SFDP` is command-mode only.** SFDP discovery covers command-based read/program but
  not the memory-mapped read command and dummy cycles used by XIP, which is why a slot left on
  `Auto_detect_SFDP` can pass API read/write tests and still return partly wrong data through an
  XIP pointer. Select the explicit part for XIP.
- **Quad-SPI protocol state can matter before first access.** In the scoped `S25HL512T` quad-SPI
  reference path, do not assume the flash is already in the required protocol state after reset.
  Bring it back to a known command state and verify quad mode before handing control to a
  configured quad read path. For the example-derived recovery sequence, see
  [example-s25hl512t.md](./example-s25hl512t.md). For the scoped timeout and clock-margin case, see
  [troubleshooting.md](./troubleshooting.md).

## Sources

Infineon datasheets for S25HL512T, S26HS/HL256T–01GT (Semper flash, HyperBus) and
S27KL0642 / S27KS0642 (HyperRAM). Per-board fitment cross-checked against the BSP repositories and
the SMIF code examples listed in [troubleshooting.md](./troubleshooting.md).
