# Configurator setup (Device Configurator + QSPI Configurator)

Contents:

- configuration layers that must agree
- Device Configurator checks and SMIF block naming
- SMIF clock-path validation and chip-frequency limits
- mandatory generated-file verification checklist
- QSPI Configurator slot checks and user handoff
- routing interpretation and topology guidance

External memory on TRAVEO T2G needs both configurators. They are different tools, edited
separately, and they generate different symbols. Having one without the other is the most common
reason the initialization code fails to compile.

| Tool | Source file | Generates | Provides |
| --- | --- | --- | --- |
| Device Configurator | `design.modus` | `cycfg_peripherals.h` | `SMIF0_HW`, `SMIF0_config`, `SMIF0_hal_config` — the SMIF block. Needed by the `serial-memory` path only |
| QSPI Configurator | `design.cyqspi` | `cycfg_qspi_memslot.h` | `smif0BlockConfig`, `smif0MemConfigs` — the memory parts on that block. Needed by both libraries |

Both are GUI-only and both are the user's to edit. Check each one and report what is missing.
Never edit `GeneratedSource/`, and never hand-edit or copy `design.modus` or `design.cyqspi`.

Board-specific values (personality name, pins, slots, XIP base) come from
[board-memory-map.md](./board-memory-map.md).

## Configuration layers that must agree

SMIF bring-up depends on multiple independent configuration surfaces. A correct QSPI slot alone
does not make external flash work on hardware. Check all of these layers together:

- Device Configurator SMIF peripheral block
- QSPI Configurator memory-slot and device settings
- generated routing and pin mapping
- generated system clock tree
- middleware / library / PDL compatibility
- application initialization code

If the project builds but external flash read/write still fails, assume at least one of these
layers disagrees with the others until proved otherwise.

## Device Configurator — enable the SMIF peripheral

> Only the `serial-memory` path needs this. The legacy `serial-flash` library takes the
> pins and bus frequency as arguments to `cy_serial_flash_qspi_init()` and sets the block up
> itself — the legacy example on KIT_T2G-B-H_LITE has zero SMIF entries in `design.modus`
> and no `SMIF0_HW`, and still works. If `serial-flash` was chosen, skip straight to the QSPI
> Configurator section.

1. Search `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_peripherals.h` for `SMIF0_HW`. If it is
   there, the block is already enabled — go to the QSPI Configurator section.
2. If it is absent, look in `design.modus` for a SMIF personality. **Do not assume the template
   name — it differs per device.** Look up the board in
   [board-memory-map.md §SMIF IP revision and Device Configurator personality](./board-memory-map.md#smif-ip-revision-and-device-configurator-personality),
   and grep for `smif` in `design.modus` rather than for a specific template name.
3. Ask the user to enable it in the Device Configurator — select the SMIF block, apply
   whichever SMIF personality that device offers, and save. Offer to launch it the same way as
   the QSPI Configurator below: list the available tools first and use the exact name reported
   for the Device Configurator.
4. If the personality exposes pin ports, have them route the pins. Enabling the personality is
   not enough on those devices; each signal must be assigned or the build succeeds and the memory
   fails at run time. Use the required-signal list and the working assignment in
   [board-memory-map.md §Pin routing](./board-memory-map.md#pin-routing).

   Route every line that the selected memory mode actually uses. The detailed lane rules are in
   [Routing interpretation and topology guidance](#routing-interpretation-and-topology-guidance).

   Routing the pin is not enough — check its drive mode. When `spihb_rwds` is added, the
   Device Configurator may give the pin `CY_GPIO_DM_ANALOG`, which disconnects it from the
   digital path and breaks DDR traffic just like not routing it at all. The
   working Infineon examples use `CY_GPIO_DM_PULLUP` for RWDS and for the chip selects, and
   `CY_GPIO_DM_STRONG` for clock and data. Confirm each pin's `DriveModes` in `design.modus`, or
   read them back from `cycfg_pins.c`. For runtime failure signatures, see
   [troubleshooting.md](./troubleshooting.md).
5. After they save, confirm `SMIF0_HW`, `SMIF0_config` and `SMIF0_hal_config` now appear in
   `cycfg_peripherals.h`. Use the names you find; a second SMIF instance appears as `SMIF1_*`.

   The generated symbol prefix comes from the block's name/alias, so have the user set it.
   With the block named `SMIF0` the tool emits `SMIF0_HW`, `SMIF0_config`, `SMIF0_hal_config` —
   the names every Infineon example uses. Leave the name blank and the same personality instead
   emits `smif_0_HW` and `SMIF_0_hal_config` (note the differing case and the extra underscore),
   and no `_config` structure at all, so the initialization code will not compile. If the user
   prefers a different name, use whatever the header declares — but `SMIF0` keeps the code
   portable between boards and examples.

## Device Configurator — validate the SMIF clock path, not just the divider

Clock validation is required for every external-memory setup. Do not stop at "the assigned
HFCLK has a divider" or "SMIF0 has a clock assigned". Prove the effective SMIF clock that the
generated project will actually use, then compare it against the selected memory part, protocol,
and explicit configurator part definition.

Inspect all of the following together:

- `design.modus`
- `GeneratedSource/cycfg_clocks.c`
- `GeneratedSource/cycfg_clocks.h`
- `GeneratedSource/cycfg_system.c` — HF clock source path and HFCLK dividers
- `GeneratedSource/cycfg_system.h`
- `GeneratedSource/cycfg_peripherals.c`
- `GeneratedSource/cycfg_peripherals.h`
- the installed PDL headers for the selected device / BSP
- an optional known-working reference project, when one is available

Trace the complete clock path in this order:

1. The active SMIF instance and its generated clock handle (`SMIF0_hal_config` or
   `SMIF1_hal_config`).
2. The SMIF clock source / assignment used by that handle.
3. The peripheral clock group and divider assigned to that SMIF path.
4. The upstream `HFCLK` source clock for that SMIF path.
5. The divider value on that `HFCLK`.
6. The final effective SMIF clock frequency at the SMIF block.

Calculate, do not guess:

```text
effective SMIF clock =
    source clock frequency
    / HFCLK divider
    / peripheral divider
```

Do not prescribe a universal MHz value unless that number has been derived from the current
generated configuration. If the source clock or divider chain cannot be established from the
generated files, stop and ask the user for the Device Configurator clock settings or a working
reference project.

Do not assume one fixed `HFCLK` for all TRAVEO T2G SMIF projects. In the observed B-H
`S25HL512T` topology, the generated path uses `HFCLK6`. On C-2D devices with two SMIF
instances, the generated path commonly maps `SMIF0` through `HFCLK8` and `SMIF1` through
`HFCLK9`. Treat those as topology-specific expectations, then confirm the exact assignment in the
generated clock and peripheral files before answering.

After calculating the effective SMIF clock, compare it against the current project's chip and
protocol. The chip-level limits belong in [memory-parts.md](./memory-parts.md); the generated part
definition in the QSPI Configurator is still authoritative for the exact slot the user selected.

Apply these chip-specific rules:

- `S25HL512T`: this skill does not publish one universal MHz limit for this part.
   Use the exact `S25HL512T` datasheet plus the explicit configurator part definition. The scoped
   observed `S25HL512T` quad-SPI reference path had to stay below **160 MHz** for runtime access
   to pass. Treat that as a path-specific observed result, not as a published chip-wide limit or a
   rule for all `S25HL512T` designs. For the divider failure case behind that number, see
   [troubleshooting.md §Clock configuration](./troubleshooting.md#clock-configuration-and-effective-smif-frequency).
- `S26HL512T` / `S26HS*`: compare the effective clock against the active protocol. From the
   Semper HYPERBUS flash datasheet (S26HS/HL256T–01GT), HyperBus read DDR runs up to **200 MHz** on HS-T parts and
   up to **166 MHz** on HL-T parts; legacy x1 SPI fast read uses up to **166 MHz**, while plain
   SPI read is listed at **50 MHz**.
- `S27KL0642` / `S27KS0642`: from the S27KL0642 / S27KS0642 HyperRAM datasheet, both variants are rated for
   **200 MHz maximum clock**.
- `S28HS512T`: keep the lane, DDR, and timing settings aligned with the explicit configurator part
   definition and the exact datasheet for the selected octal-DDR configuration. This skill does not
   prescribe one universal MHz number for all `S28HS512T` topologies.

Use these additional checks only for the scoped `S25HL512T` quad-SPI reference path:

- The generated peripheral clock configuration must match the path used by `SMIF0_hal_config`.
- The real constraint is the final effective SMIF clock frequency, not the divider number by
   itself.
- Keep the rule at the effective-frequency level. The observed divider-specific failure case
   belongs in [troubleshooting.md](./troubleshooting.md).

If the project uses a different SMIF IP revision, a different lane topology, a different SMIF
instance, or a different generated clock path, treat the threshold above as a reference case, not
as a universal requirement. Recalculate from that project's generated files.

## Mandatory generated-file verification checklist

After any Device Configurator or QSPI Configurator change, re-open the generated files and verify
that the expected fields changed. Do not trust the GUI save by itself.

| Generated file | What must be verified |
| --- | --- |
| `cycfg_peripherals.c/h` | SMIF block exists, SMIF instance is the intended one, selected HF clock handle matches expectations, enabled data lines and chip-selects match the intended memory topology |
| `cycfg_qspi_memslot.c/h` | memory command set, address width, data width, erase and program commands, memory-mapped flags, merge timeout, base address, and block/slot symbols match the intended part and slot |
| `cycfg_routing.h` | actual assigned `CLK`, `CS`, `DATA`, and `RWDS` pins match the intended topology |
| `cycfg_system.c/h` | actual HF clock source path, HFCLK divider, and resulting frequency match the intended SMIF clock tree |
| `cycfg_clocks.c/h` | peripheral clock group and divider on the SMIF path match the intended SMIF clock tree |

If the generated files do not reflect the intended settings, stop and fix the configurator input.
Do not patch `GeneratedSource/` by hand.

## QSPI Configurator — configure the memory slots

The memory part, its slot, its memory-mapped (XIP) start address and its size all come from the
QSPI Configurator, not from code.

Expect there to be nothing configured yet. Most TRAVEO T2G BSPs ship either no
`design.cyqspi` at all or one with every slot set to `Not used`; the SMIF code examples supply
their own under `templates/`. Creating the slot configuration is the normal path on T2G, not an
edge case.

1. Look for `design.cyqspi` in `bsps/TARGET_<bsp>/config/`, and for an app-level override in
   `templates/TARGET_<bsp>/config/`. An app-level `templates/` copy wins for that target.
2. Read the slot entries. For each slot record `SlaveSlot`, `MemoryId`, `MemoryMapped`,
   `StartAddress`, `Size`, `WriteEnable`, `DataSelect`. Report this table to the user.
3. Confirm a slot exists for the memory the user wants. For flash, do not treat `WriteEnable` as
   a universal rule. Match the exact project or known-good reference configuration instead.
   `WriteEnable` controls write access in memory-mapped (XIP) mode; it is not, by itself, a
   prerequisite for flash erase/program operations done through the API path. So for XIP flash
   slots, follow the proven project/reference setting carefully. For simple non-XIP API read/write
   flows, do not force `WriteEnable` unless the project or reference configuration shows that it is
   needed. For PSRAM, do not blindly apply the flash rule: the CE241382
   `S27KL0642` configuration (KIT_T2G_C-2D-4M_LITE) writes successfully with `WriteEnable = false`,
   while the CE241382 `S27KS0642` configuration (KIT_T2G_C-2D-6M_LITE) has it enabled. In both cases, require `MemoryMapped` only when
   the project intends to use XIP. Prefer an explicit memory part whenever the exact fitted chip
   is known and can be selected in the QSPI Configurator.

   > If the slot still uses `Auto_detect_SFDP`, treat it as a generic placeholder. Replace it with
   > the explicit part definition when the exact fitted chip is known. This is especially important
   > for XIP: SFDP supplies command-based access parameters, but the memory-mapped read command and
   > its dummy cycles are not necessarily correct for the fitted part. For the common XIP failure
   > signature from a generic SFDP slot, see [troubleshooting.md](./troubleshooting.md).

   Do not guess a specific memory definition from a generic SFDP slot. If the project, the user's
   stated part number, or a known-good reference configuration already identifies the exact flash
   definition, use it instead. Otherwise, report that the slot is still generic and ask the user
   to confirm the exact fitted part before prescribing a chip-specific replacement.
4. If no suitable slot exists, the user must create it in the QSPI Configurator GUI.

   > **This is a hard stop, and the agent cannot do it.** Creating or editing a slot requires the
   > GUI. `qspi-configurator-cli` only *regenerates* `cycfg_qspi_memslot.*` from a `design.cyqspi`
   > that already exists (`--config <file> --output-dir <dir>`); it cannot add a memory or change a
   > slot. Do not work around this by copying a `design.cyqspi` from another application or code
   > example — the slot layout is board- and part-specific.

   Give the user a filled-in settings table before they open the tool, using values from
   [board-memory-map.md](./board-memory-map.md) (or from the memory part they name if the board is
   not listed):

   | Field | Value to enter |
   | --- | --- |
   | Slave slot | the slot for this memory on this board |
   | Memory | the exact part, e.g. `S28HS512T (Octal DDR Hybrid at Bottom)` |
   | Memory Mapped | checked, if XIP is wanted |
   | Start Address | the XIP base for that slot |
   | Write Enable | controls write access in memory-mapped (XIP) mode only; not required for API erase/program or for PSRAM by itself — match the proven project/reference setting (see step 3) |
   | Data Select | e.g. `OCTAL_SPI_DATA_0_7` or `QUAD_SPI_DATA_0_3` |

   If `design.modus` still has no SMIF personality or no generated `SMIF0_*` / `SMIF1_*`
   symbols for the intended instance, stop here and complete the Device Configurator section
   first. The QSPI slot configuration alone is not enough.

   On a board with two flash devices, repeat this for the second slot with its own data select
   and chip select — one slot gives access to one device only.

   Then ask which they prefer:

    - "Launch it for me" → run `python .github/skills/mtb-tools/scripts/run_tool.py` with no
       argument first to list the available GUI tools, then invoke it by the exact name reported.
    - "I'll open it myself" → wait for the user to confirm they have saved the configuration.

   Either way, stop here and wait. When the user returns, re-run steps 1-3 above to confirm the
   slot is present before continuing.
5. Read `GeneratedSource/cycfg_qspi_memslot.h` and note the actual generated symbol names for
   this board. They differ per device and per SMIF instance — for example a second SMIF block may
   produce a separate block config symbol. Use the names you found, never invented ones. The SMIF
   IP revision is not the same across the TRAVEO T2G families, so the QSPI Configurator
   personality — and with it the generated symbols and the available features — varies by device.

Take the XIP base address from the slot's `StartAddress`. Do not hardcode an address from an
example or from memory.

## Routing interpretation and topology guidance

Interpret generated routing according to the memory mode, not by copying every signal from a
reference project.

- `DATA0` / `DATA1` only is sufficient for single or dual data-line modes that actually use those
   lanes. If the slot uses those lanes, the same pins must be explicitly assigned to SMIF in the
   Device Configurator.
- `DATA0` ... `DATA3` matter for quad-SPI flash modes.
- `DATA4` ... `DATA7` matter only for wider interfaces that actually use the upper lane group.
- Any lane group selected in the slot configuration must also be present in the generated routing.
  Do not assume the configurator inferred the pins from `Data Select`; verify them in
  `design.modus`, `cycfg_routing.h`, or both.
- `RWDS` matters for HyperBus, HyperRAM, and DDR-capable flash modes that use a strobe; it does
   not become mandatory just because a different reference project routes it.
- A reference project may include extra routing because it also supports PSRAM, HyperBus, or a
   second flash device. Do not copy extra signals blindly without matching them to the memory mode
   the current project actually uses.

When comparing against a known-good project, identify which signals belong to the current flash
mode and which belong to a different topology.
