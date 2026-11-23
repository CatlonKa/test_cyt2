---
name: mtb-smif-storage
description: "Use when the user needs external QSPI/Octal NOR flash or HyperRAM PSRAM on a TRAVEO T2G board (KIT_T2G-B-H, KIT_T2G_C-2D) through SMIF, including serial-memory or serial-flash setup, QSPI Configurator memory slots, XIP memory-mapped access, or reading, writing and erasing external memory."
license: "Apache-2.0"
metadata:
   author: "Infineon ModusToolbox Team"
   version: "1.1.0"
---

# SMIF external flash / PSRAM storage (TRAVEO T2G)

Set up external serial memory on a TRAVEO T2G application through the SMIF (Serial Memory
Interface) block: external NOR flash or external PSRAM, accessed either through library calls
or memory-mapped in XIP mode.

Two libraries can drive the SMIF block and they are mutually exclusive, so the first job is to
establish which one this project will use. If the project already uses one, keep it. If it uses
neither, default to `serial-memory` and install it — see Step 1 for the full rule and the one
case where that default does not apply.

## Non-negotiable rules

1. **Detect first, then write.** Never assume a library, slot, chip select, or XIP address.
2. **The configurators are GUI-only.** Never hand-edit `GeneratedSource/`, `design.modus`, or
   `design.cyqspi`; inspect them, tell the user exactly what to change, then wait for save and
   regeneration.
3. **Never mix `serial-memory` and `serial-flash`.** Keep one middleware path only.
4. **Use `serial-memory` `release-v2.0.0` for this SMIF flow.** Newer `serial-memory` releases
   are not supported for this SMIF flow. If the project is pinned to a different release, stop and
   switch it first — see
   [library-selection.md §Pin serial-memory to release-v2.0.0](./references/library-selection.md#pin-serial-memory-to-release-v200).
5. **Read installed headers, not memory.** Match the exact installed function signatures and the
   generated symbol names declared for this project.
6. **Treat SMIF as layered hardware configuration.** Slot configuration alone is not enough;
   peripheral enable, routing, clocks, middleware compatibility, and init code must agree.
7. **Fix configurator state at the source.** Do not work around bad clocks, pins, or routing in
   application code.

## When to use

- "read/write external flash", "add PSRAM", "add QSPI storage", "configure SMIF storage",
  "external memory access", "store data in external memory", "enable XIP"
- The user wants to place data (or code) in an external memory-mapped region on a T2G board.
- The project already has a working SMIF setup and the user only wants to swap the memory part
  on the same board topology, library path, and interface mode: skip Steps 1 and 4, start at
  Step 3 with the QSPI Configurator slot, then re-check the chip limits from Step 2 and re-run
  Step 6.

## When not to use

- Internal (on-chip) flash / work flash programming — that is the flash PDL driver, not SMIF.
- Emulated EEPROM or key-value storage on internal flash.

## Prerequisites

- A ModusToolbox application targeting a TRAVEO T2G board, with `make getlibs` already run.
- The board must physically have the external memory the user is asking for.
- In a multi-project application, identify the single project that owns the SMIF block before
   editing anything.

## Workflow

### Step 1 — Decide which SMIF library this project uses

Use [library-selection.md](./references/library-selection.md) to detect the active middleware from
`deps/`, source includes, API usage, HAL flavour, and generated symbols. Default to
`serial-memory` only when neither library is present and the legacy path is not explicitly needed.

### Step 2 — Decide flash vs PSRAM

Treat flash and PSRAM as different bring-up paths. Use
[board-memory-map.md](./references/board-memory-map.md) for board-specific slot, chip-select,
data-select, and XIP-address values, and use [memory-parts.md](./references/memory-parts.md) for
chip-level behaviour such as erase rules, interface mode, and recovery flow.

### Step 3 — Configure the hardware in the two configurators

Use [configurators.md](./references/configurators.md) for the exact GUI settings, generated-file
checks, routing requirements, and clock-path validation. The main rules are:

1. creating or editing a slot is a GUI-only hard stop
2. the Device Configurator block should be named `SMIF0` when that instance is used
3. every signal used by the selected memory mode must be assigned to SMIF pins in Device
   Configurator; for example, if the slot uses `DATA0` / `DATA1`, those pins must be routed for
   SMIF, and DDR parts also require `spihb_rwds` to be routed and given a digital drive mode

After the user saves, re-read the generated headers and use the symbol names and `StartAddress`
values the project actually generated.

### Step 4 — Apply build and dependency wiring

Use [library-selection.md](./references/library-selection.md) for the `serial-memory`
`release-v2.0.0` pin, `Makefile` changes, required defines, and dependency checks.

### Step 5 — Write initialization and access code

Use [code-patterns.md](./references/code-patterns.md) for initialization, flash access, PSRAM
access, XIP access, runtime diagnostics, and behavior-scoped validation. If the current project
matches one of the extracted reference examples, also read the chip-specific note linked from
[code-patterns.md](./references/code-patterns.md). If Step 1 selected the legacy path, use
[legacy-api.md](./references/legacy-api.md) instead.

### Step 6 — Validate behavior

Use the verification checklist in [code-patterns.md](./references/code-patterns.md) and the
failure analysis in [troubleshooting.md](./references/troubleshooting.md). Do not declare success
from build alone; require behavior-scoped runtime checks.

## Reference map

Read the referenced file before acting on that surface. Do not infer board-specific or chip-
specific values from memory.

| Need | Reference |
| --- | --- |
| detect the active middleware, interpret HAL flavour, update `Makefile` | [library-selection.md](./references/library-selection.md) |
| choose slot, chip select, data select, XIP base, or derive a custom board mapping | [board-memory-map.md](./references/board-memory-map.md) |
| understand chip behaviour such as erase rules, interface mode, recovery, or timeout signatures | [memory-parts.md](./references/memory-parts.md) |
| tell the user what to change in Device Configurator or QSPI Configurator | [configurators.md](./references/configurators.md) |
| write generic init, flash, PSRAM, XIP, diagnostics, or validation code | [code-patterns.md](./references/code-patterns.md) |
| apply example-derived code notes for a matching chip/topology only | the chip-specific example note linked from [code-patterns.md](./references/code-patterns.md) |
| stay on the legacy `serial-flash` path | [legacy-api.md](./references/legacy-api.md) |
| debug a project that builds but still fails on hardware | [troubleshooting.md](./references/troubleshooting.md) |

If the user's project disagrees with anything in these files, the project wins — re-read its
headers and generated configuration and say so.

