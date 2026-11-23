# `S27KL0642` / `S27KS0642` example-derived code notes

Use this note only when the project matches the same chip family and generated PSRAM topology as
the Infineon `mtb-example-ce241382-smif-psram-readwrite` configurations for
KIT_T2G_C-2D-4M_LITE and KIT_T2G_C-2D-6M_LITE.

## Extracted facts from the reference projects

- Both examples use `SMIF1_*` symbols and `smif1BlockConfig`, not `SMIF0`.
- Both examples pass `MTB_SERIAL_MEMORY_CHIP_SELECT_1` to `mtb_serial_memory_setup()`. That
  matches the 6M slot (`CY_SMIF_SLAVE_SELECT_1`) but not the 4M slot (`CY_SMIF_SLAVE_SELECT_0`);
  the 4M example works only because `smif1BlockConfig` holds a single memory and setup falls
  back to it.
- Both examples disable both instruction and data cache (`SCB_DisableICache()`,
  `SCB_DisableDCache()`) before using the XIP-mapped PSRAM path.
- Both generated HyperBus device configs use wrapped-burst XIP read/write commands and
  `dummyCycles = 14`.
- The 4M example configures `S27KL0642` on slot 4, with `slaveSelect = CY_SMIF_SLAVE_SELECT_0`,
  `baseAddress = 0x80000000`, and `memMappedSize = 0x10000`.
- The 6M example configures `S27KS0642 (166 MHz)` on slot 5, with
  `slaveSelect = CY_SMIF_SLAVE_SELECT_1`, `baseAddress = 0x80000000`, and
  `memMappedSize = 0x4000000`.
- The 4M example writes successfully even though the slot has no write-enable flag, while the 6M
  example's generated flags include write-enable.
- Both examples validate PSRAM by API write/read first, then enable XIP and perform pointer-based
  write/read at the mapped base address.

## Code guidance derived from those facts

- Do not assume a PSRAM project will use `SMIF0`. On these C-2D examples, PSRAM is brought up
  on `SMIF1`, so the correct generated symbols are `SMIF1_HW`, `SMIF1_config`,
  `SMIF1_hal_config`, and `smif1BlockConfig`.
- Set `MTB_SERIAL_MEMORY_CHIP_SELECT_<n>` to match the PSRAM slot's `slaveSelect` in
  `cycfg_qspi_memslot.c` (`CY_SMIF_SLAVE_SELECT_0` → `..._CHIP_SELECT_0`,
  `CY_SMIF_SLAVE_SELECT_1` → `..._CHIP_SELECT_1`). Do not derive it from the QSPI slot number,
  and do not copy `CHIP_SELECT_1` from the example onto a board whose slot uses select 0.
- Do not generalize flash-style `WriteEnable` rules to PSRAM. Read the generated HyperBus part and
  flags from the actual project instead of assuming that PSRAM write support is gated the same way
  on every board.
- If PSRAM XIP reads or writes behave inconsistently, inspect cache state first. Both CE241382
  configurations (`S27KL0642` and `S27KS0642`) disable I-cache and D-cache before mapped access.