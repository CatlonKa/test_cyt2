# `S26HL512T` example-derived code notes

Use this note only when the project matches the same chip family and generated slot topology as
the KIT_T2G_C-2D-4M_LITE `design.cyqspi` shipped with the Infineon SMIF code examples (for
example `mtb-example-ce241382-smif-psram-readwrite`).

## Extracted facts from the reference project

- `design.cyqspi` slot 0 uses `MemoryId = S26HL512T (Hybrid at Top)`.
- `design.cyqspi` slot 0 uses `DataSelect = SPI_MOSI_MISO_DATA_0_1`.
- Generated `readCmd`, `programCmd`, and `eraseCmd` use single-width command, address, and data
  transfers.
- The same project also configures `S27KL0642` on slot 4 with `DataSelect = OCTAL_SPI_DATA_0_7`.

## Code guidance derived from those facts

- Do not assume HYPERBUS just from the part number. Read the generated slot and command widths
  first.
- When the generated flash slot is single-width like this example, the ordinary
  `mtb_serial_memory_erase()` / `mtb_serial_memory_write()` / `mtb_serial_memory_read()` flow is
  the right default code path after `mtb_serial_memory_setup()`.
- This project also carries `S27KL0642` on `SMIF1` in the generated configuration. Keep the flash
  path and the PSRAM path separate; do not infer the flash lane width from the PSRAM topology.