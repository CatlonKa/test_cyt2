# `S28HS512T` example-derived code notes

Use this note only when the project matches the same chip family and generated slot topology as
the KIT_T2G_C-2D-6M_LITE reference project this note was extracted from.

## Extracted facts from the reference project

- `design.cyqspi` slot 0 uses `MemoryId = S28HS512T (Octal DDR Hybrid at Bottom)`.
- `design.cyqspi` slot 0 uses `DataSelect = OCTAL_SPI_DATA_0_7`.
- Generated flash commands use octal command width and octal address/data paths with DDR timing.
- The example calls `Cy_SMIF_Reset_Memory()` after `Cy_SMIF_Enable()` and before
  `mtb_serial_memory_setup()`.
- The example uses `Cy_SMIF_MemCmdWriteEnable()`, `Cy_SMIF_MemCmdSectorErase()`, and
  `Cy_SMIF_MemCmdProgram()` for erase/program operations, with explicit wait delays.

## Code guidance derived from those facts

- Treat this as an octal-DDR flash path. Do not reuse single-line or quad-SPI assumptions from
  other parts.
- In projects that use `serial-memory`, prefer the middleware APIs for normal access:
  `mtb_serial_memory_read()`, `mtb_serial_memory_write()`, and
  `mtb_serial_memory_erase()`. Do not copy the direct PDL erase/program sequence as the default
  application path.
- Use the reset-before-setup pattern only when the same fixed explicit-part configuration needs a
  known command/protocol state before the middleware starts using it.
- Treat the direct PDL erase/program sequence plus explicit delays as a topology-specific fallback,
  reference detail, not as the default write path for all SMIF flash parts.