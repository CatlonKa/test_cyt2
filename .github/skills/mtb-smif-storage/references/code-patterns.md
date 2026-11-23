# Code patterns

Contents:

- Initialization — current library (`serial-memory`)
- chip-specific reference example map
- temporary runtime diagnostics
- behavior-scoped validation sequence
- verification checklist
- Access — flash (erase → write → read)
- Access — PSRAM (write → read, no erase)
- Access — XIP (memory-mapped)

Apply the patterns below as normal edits in the user's project. Do not edit generated files, and
do not paste these blocks verbatim without adapting the symbols, signatures and addresses to the
project you just inspected.

Board-specific values (chip select, slot, XIP base) come from
[board-memory-map.md](./board-memory-map.md) and from the project's own `design.cyqspi`.

## Initialization — current library (`serial-memory`)

Order matters: PDL SMIF init and enable first, then the library setup.

```c
#include "cy_pdl.h"
#include "cybsp.h"
#include "cycfg_qspi_memslot.h"   /* QSPI Configurator output */
#include "mtb_serial_memory.h"

#define SMIF_INIT_TIMEOUT_US (1000u)   /* Infineon reference projects use 1000u-10000u */

cy_stc_smif_context_t smif_context;
mtb_serial_memory_t   serial_memory_obj;

/* <SMIF_HW>, <SMIF_CONFIG> and <SMIF_HAL_CONFIG> come from cycfg_peripherals.h (Device
 * Configurator); <BLOCK_CONFIG> comes from cycfg_qspi_memslot.h (QSPI Configurator).
 * Use the symbols those headers actually declare for this board and SMIF instance.
 * cycfg_qspi_memslot.h also defines the aliases `smifBlockConfig` -> `smif0BlockConfig` and
 * `smifMemConfigs` -> `smif0MemConfigs`; those short names exist for SMIF0 only, so a second
 * SMIF instance must be addressed as smif1BlockConfig. */
cy_en_smif_status_t smif_status =
    Cy_SMIF_Init(<SMIF_HW>, &<SMIF_CONFIG>, SMIF_INIT_TIMEOUT_US, &smif_context);
/* handle smif_status */

Cy_SMIF_Enable(<SMIF_HW>, &smif_context);

cy_rslt_t result = mtb_serial_memory_setup(&serial_memory_obj,
                                           MTB_SERIAL_MEMORY_CHIP_SELECT_<n>,
                                           <SMIF_HW>,
                                           <SMIF_HAL_CONFIG>.clock,
                                           &smif_context,
                                           &<BLOCK_CONFIG>);
/* handle result */
```

Before emitting this, open
`../mtb_shared/serial-memory/release-v2.0.0/include/mtb_serial_memory.h` and match the
signatures exactly. In `release-v2.0.0`, `mtb_serial_memory_setup()` is:

```c
cy_rslt_t mtb_serial_memory_setup(mtb_serial_memory_t* obj,
                                  mtb_serial_memory_chip_select_t smif_active_chip,
                                  SMIF_Type* base,
                                  const mtb_hal_clock_t* clock,
                                  cy_stc_smif_context_t* context,
                                  const cy_stc_smif_block_config_t* block_config);
```

If the project resolves to a different `serial-memory` release, stop and pin it first — see
[library-selection.md](./library-selection.md#pin-serial-memory-to-release-v200).

Useful queries in `release-v2.0.0`:
`mtb_serial_memory_get_size()`, `mtb_serial_memory_get_erase_size()`,
`mtb_serial_memory_get_prog_size()`, `mtb_serial_memory_get_active_chip()`,
`mtb_serial_memory_get_chip_count()`.

`MTB_SERIAL_MEMORY_CHIP_SELECT_n` is a bitmask (`_0 = 1`, `_1 = 2`, `_2 = 4`, `_3 = 8`) and must
equal the slot's `slaveSelect` (`CY_SMIF_SLAVE_SELECT_n`) in `cycfg_qspi_memslot.c` — derive it
from there, not from the QSPI slot number. `mtb_serial_memory_get_active_chip()` returns that
bitmask, not an index: `..._CHIP_SELECT_0` reports 1, `..._CHIP_SELECT_1` reports 2,
`..._CHIP_SELECT_2` reports 4.

`mtb_serial_memory_setup()` does not reject a chip select that matches no slot's `slaveSelect`;
it falls back to the first memory in the block config. With one memory in the block this still
works and hides the mistake; with two memories it silently talks to the wrong device.

On a board with two flash devices, each device needs its own chip select and its own
`mtb_serial_memory_t` setup — see [board-memory-map.md](./board-memory-map.md).

If the project uses the legacy `serial-flash` path, use
[legacy-api.md](./legacy-api.md) instead of the patterns below.

## Chip-specific reference example map

Keep this file generic. Read a chip-specific example note only when the user's project matches the
same chip family and generated slot topology.

Available example-derived notes:

- [example-s25hl512t.md](./example-s25hl512t.md) — B-H-family `S25HL512T` quad-SPI reference pattern
- [example-s26hl512t.md](./example-s26hl512t.md) — C-2D-4M `S26HL512T` single-width flash pattern
- [example-s27k-psram.md](./example-s27k-psram.md) — `S27KL0642` / `S27KS0642` PSRAM patterns
- [example-s28hs512t.md](./example-s28hs512t.md) — C-2D-6M `S28HS512T` octal-DDR flash pattern

Those files distinguish between extracted facts from the reference projects and code guidance
derived from those facts. Do not apply them unless the current project matches the same memory
part and generated configuration style.

## Temporary runtime diagnostics

First inspect the generated configuration files. The expected clock path, divider chain, SMIF
clock handle, slot layout, and XIP base should be read from `cycfg_system.*`,
`cycfg_peripherals.*`, `cycfg_qspi_memslot.*`, and `cycfg_routing.h` before asking the user to
run anything.

Only when the project builds, the generated files look correct, and hardware behavior is still
wrong should the agent ask for temporary UART logging. Use runtime prints to prove what the
running image is actually using and to catch cases where the running hardware behavior disagrees
with the generated configuration:

- HF clock index used by SMIF
- HF source enum or source path
- HF divider
- HF output frequency
- PERI frequency seen by the SMIF path

Use these prints to compare the running project against the generated `cycfg_system.*` and
`cycfg_peripherals.*` files first, and then against a known-good local reference project when one
exists.

## Behavior-scoped validation sequence

Use this order when validating flash behavior after setup:

1. initialize SMIF
2. erase the target region
3. read the erased region and verify `0xFF`
4. write a deterministic raw-byte pattern
5. read back the raw bytes
6. compare the buffers directly
7. only then run digest, hash, filesystem, or higher-level validation

Do not collapse these checks into a single pass/fail result:

- erase success does not prove reads are correct
- write success does not prove the interface is correct
- raw byte comparison is mandatory before concluding higher-level logic is broken

## Verification checklist

Use this checklist before declaring the setup finished. The agent should verify everything it can
from the project's files first; only ask the user to run build, program, or runtime checks for
behavior that cannot be proven statically:

1. build the project and confirm there are no unresolved symbols for the selected library
2. confirm the build links only one SMIF middleware path, not both `serial-memory` and
    `serial-flash`
3. if external-memory programming is required, program the image and confirm the tool reports
    writing the external region
4. confirm setup returns `CY_RSLT_SUCCESS`
5. confirm `mtb_serial_memory_get_size()` reports the device capacity, not the slot `Size`
6. for flash, validate `erase -> raw read 0xFF -> raw write -> raw read-back -> buffer compare`
7. for PSRAM, validate `write -> read -> buffer compare`, and remember the contents are volatile
8. only after raw-byte validation passes, move on to filesystem, digest, hash, or other
    higher-level checks
9. if XIP is enabled, read the same data through a pointer at the slot `StartAddress` and confirm
    it matches the API-based read path

Do not treat a mismatch between slot `Size` and `mtb_serial_memory_get_size()` as an error by
itself. The API reports the memory device's capacity, not the configurator window.

## Access — flash (erase → write → read)

```c
uint32_t erase_size = mtb_serial_memory_get_erase_size(&serial_memory_obj, address);
result = mtb_serial_memory_erase(&serial_memory_obj, address, erase_size);
result = mtb_serial_memory_write(&serial_memory_obj, address, length, tx_buf);
result = mtb_serial_memory_read (&serial_memory_obj, address, length, rx_buf);
```

Erase before write is mandatory, the erase address must be sector-aligned, and the erase affects
the whole sector — warn the user if their target range shares a sector with other data.

Always take the size from `mtb_serial_memory_get_erase_size()` for the specific address; never
assume a constant. At address 0 the same 512 Mbit part class erases **262144 bytes** on
KIT_T2G_C-2D-4M_LITE (S26HL512T, hybrid at top) but only **4096 bytes** on KIT_T2G_C-2D-6M_LITE
(S28HS512T, hybrid at bottom) — a 64x difference driven purely by where the hybrid small-sector
region sits.

## Access — PSRAM (write → read, no erase)

```c
result = mtb_serial_memory_write(&serial_memory_obj, address, length, tx_buf);
result = mtb_serial_memory_read (&serial_memory_obj, address, length, rx_buf);
```

Do not write an erase call for PSRAM.

## Access — XIP (memory-mapped)

```c
result = mtb_serial_memory_enable_xip(&serial_memory_obj, true);
volatile uint8_t *mapped = (volatile uint8_t *)<slot StartAddress from design.cyqspi>;
```

After enabling XIP the memory is reachable through ordinary pointer access at the slot's start
address. Flash mapped this way is read-only for normal stores — writes still go through the
erase/write API. PSRAM mapped this way is readable and writable in place.

Caches sit between the core and the SMIF region on the CM7 cores. If the user reads back stale
data after a non-XIP write, or writes through XIP that do not land, cache maintenance is the
first thing to investigate:

- simplest, as the CE241382 PSRAM example does: call `SCB_DisableDCache()` before the
  external-memory test
- targeted: after an API write, call `SCB_InvalidateDCache_by_Addr(<xip addr>, <len>)` before
  reading through the XIP pointer; after writing PSRAM through the XIP pointer, call
  `SCB_CleanDCache_by_Addr(<xip addr>, <len>)` before another master or an API read uses it

The `_by_Addr` calls work on 32-byte cache lines, so align the address and length to 32 bytes.

XIP needs an **explicitly selected memory part** in the QSPI Configurator; an `Auto_detect_SFDP`
slot is not sufficient. See [configurators.md](./configurators.md).
