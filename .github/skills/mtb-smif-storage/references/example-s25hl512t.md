# `S25HL512T` example-derived code notes

Use this note only when the project matches the same chip family and generated slot topology as
the Infineon `mtb-example-ce241383-smif-flash-readwrite` code example on KIT_T2G_B-H-16M_LITE.

## Extracted facts from the reference project

- `design.cyqspi` slot 0 uses `MemoryId = S25HL512T (Hybrid at Bottom)`.
- `design.cyqspi` slot 0 uses `DataSelect = QUAD_SPI_DATA_0_3`.
- Generated flash commands use a quad read path (`cmdWidth = single`, `addrWidth = quad`,
  `modeWidth = quad`, `dataWidth = quad`) while erase, program, and write-enable commands remain
  single-width SDR commands.
- The example calls `enable_quad_mode(smifBlockConfig.memConfig[0])` before
  `mtb_serial_memory_setup()`.
- The helper resets the memory to a known command state, reads the QUAD-enable bit twice, retries
  a limited number of times, and uses a long timeout because this part stores the QUAD bit in a
  non-volatile configuration register.
- The runtime validation order is `erase -> raw read 0xFF -> raw write -> raw read-back -> XIP
  read-back`.

## Code guidance derived from those facts

- When the generated `S25HL512T` read path depends on quad data lines, do not assume the flash is
  already in the required protocol state after reset. Bring it to a known command state and verify
  that quad mode is really enabled before letting the middleware use the configured quad read path.
- For flash XIP validation, treat XIP as a read-back path after API erase/write. Do not model
  normal flash programming as direct stores through the XIP pointer.