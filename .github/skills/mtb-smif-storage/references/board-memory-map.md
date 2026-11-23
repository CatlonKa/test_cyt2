# TRAVEO T2G board → SMIF memory map

Contents:

- memory parts per board
- configured slots, data select and XIP base
- SMIF IP revision and Device Configurator personality
- pin routing
- HAL flavour per board — which SMIF library can build
- custom or unlisted boards

Everything a board-specific decision depends on: which memory parts are fitted, how many, which
slot and XIP address they use, which SMIF IP revision the device has, and which pins are routed.

The project's own configuration is always authoritative. Use this file to sanity-check an
answer and to pre-fill a settings table for the user — never to skip reading `design.cyqspi`,
`design.modus` and `cycfg_qspi_memslot.h`.

If the user's board is not listed here, it is still supported — see "Custom or unlisted boards" at
the end of this file. Do not guess values from a neighbouring row.

## Memory parts per board

Which physical memory devices are on the kit.

| Board | External NOR flash | NOR flash count | External PSRAM | PSRAM count |
| --- | --- | --- | --- | --- |
| KIT_T2G-B-H_LITE | S25HL512T | 2 | none | 0 |
| KIT_T2G_B-H-16M_LITE | S25HL512T | 2 | none | 0 |
| KIT_T2G-B-H_EVK | S25HL512T | 1 | none | 0 |
| KIT_T2G_C-2D-4M_LITE | S26HL512T | 1 | S27KL0642 | 1 |
| KIT_T2G_C-2D-6M_LITE | S28HS512T | 1 | S27KS0642 | 1 |
| KIT_T2G_C-2D-6M-DDR_LITE | S28HS512T | 1 | S27KS0642 | 1 |

Notes:

- Only the C-2D family carries PSRAM. The B-H kits are flash-only, so a request to
  "add PSRAM" on those boards has no hardware to target — say so instead of writing code.
- Two flash devices means two chip selects, not one part twice the size. On the B-H kits the
  second device sits on the upper data lines (`QUAD_SPI_DATA_4_7`) with its own select line, so
  it needs its own slot in the QSPI Configurator and its own
  `MTB_SERIAL_MEMORY_CHIP_SELECT_<n>` at setup. Configuring one device does not give access to
  the other.
- The part number tells you the interface family: `S25HL*` is SPI / dual / quad Semper NOR flash,
  `S26HL*` / `S26HS*` are HYPERBUS-or-x1-SPI Semper NOR flash, `S28HS*` is Octal DDR flash, and
  `S27K*` is HyperRAM PSRAM. A DDR or HyperBus part needs the strobe signal routed — `RWDS` on
  HyperRAM, `DS` on Semper HYPERBUS flash. Full part properties are in
  [memory-parts.md](./memory-parts.md).

## Configured slots, data select and XIP base

Taken from the SMIF code examples' `templates/TARGET_<board>/config/design.cyqspi` and from the
BSP repositories. The second flash device on the B-H kits needs its own slot on
`QUAD_SPI_DATA_4_7` — see the notes above.

| Board | Flash slot | PSRAM slot |
| --- | --- | --- |
| KIT_T2G_C-2D-4M_LITE | slot 0, `SPI_MOSI_MISO_DATA_0_1`, XIP `0x6000_0000` | slot 4, `S27KL0642`, `OCTAL_SPI_DATA_0_7`, XIP `0x8000_0000` |
| KIT_T2G_C-2D-6M_LITE | slot 0, `OCTAL_SPI_DATA_0_7` (Octal DDR), XIP `0x6000_0000` | slot 5, `S27KS0642`, `OCTAL_SPI_DATA_0_7`, XIP `0x8000_0000` |
| KIT_T2G_C-2D-6M-DDR_LITE | slot 0, `SPI_MOSI_MISO_DATA_0_1`, XIP `0x6000_0000` | slot 5, `OCTAL_SPI_DATA_0_7`, XIP **`0xC000_0000`** |
| KIT_T2G-B-H_LITE | slot 0, `QUAD_SPI_DATA_0_3`; slot 1, `QUAD_SPI_DATA_4_7`; XIP `0x6000_0000` | — |
| KIT_T2G-B-H_EVK | slot 0, `QUAD_SPI_DATA_0_3`, XIP `0x6000_0000` | — |
| KIT_T2G_B-H-16M_LITE | slot 0, `QUAD_SPI_DATA_0_3`, XIP `0x6000_0000` | — |

Traps this table exists to prevent:

- The same code example uses a different slot number for PSRAM depending on the board
  (slot 4 on the 4M, slot 5 on the 6M). Never carry a slot or chip-select constant over from an
  example — re-read it from the project.
- The PSRAM XIP base differs per board (`0x8000_0000` on C-2D-4M/6M, `0xC000_0000` on
  C-2D-6M-DDR). Never hardcode it; take it from the slot's `StartAddress`.
- The PSRAM examples also differ in configurator details that are easy to overgeneralize:
  the 4M example uses `S27KL0642` on slot 4 / slave select 0, while the 6M example uses
  `S27KS0642` on slot 5 / slave select 1. Read the exact part definition and slot from the
  project instead of copying them across boards.
- For the boards listed in this file, the fitted chip family is already known from the BSPs and
  reference projects. When the QSPI Configurator offers the exact fitted part definition, prefer
  it over `Auto_detect_SFDP`. Keep `Auto_detect_SFDP` only when the exact part definition is not
  available in the configurator, or when the board is unlisted and the exact fitted device has not
  been confirmed yet.

## SMIF IP revision and Device Configurator personality

The TRAVEO T2G families do not share a SMIF IP revision, so the personality template name,
the block path and whether pins must be routed all differ. Read the revision from
`DEVICE_<part>_IPBLOCKS` in the BSP's `bsp.mk`.

| Board | SMIF IP | Personality template | Block location | Pin routing |
| --- | --- | --- | --- | --- |
| KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-6M-DDR_LITE | `MXSMIF_V4` | `smif_core` | `smif[0].core[0]` | explicit — must be assigned |
| KIT_T2G_C-2D-4M_LITE | `MXSMIF_V3` | `mxs40smif_ver2` | `smif[0]` | none — pins are dedicated |
| KIT_T2G-B-H_LITE, KIT_T2G-B-H_EVK, KIT_T2G_B-H-16M_LITE | `MXSMIF_VER2_S40E_V2` | `mxs40smif_ver2` | `smif[0]` | none — pins are dedicated |

Grep for `smif` in `design.modus` rather than for a specific template name. A plain application
template normally has none — a Hello World on KIT_T2G_C-2D-6M_LITE contains zero SMIF entries.

## Pin routing

Only needed where the personality exposes pin ports (see the table above).

No manual pin routing is needed on KIT_T2G_C-2D-4M_LITE, KIT_T2G-B-H_LITE,
KIT_T2G-B-H_EVK and KIT_T2G_B-H-16M_LITE because those boards use dedicated SMIF pins for the
relevant personality. The explicit routing table below applies only to the `smif_core`
personality on KIT_T2G_C-2D-6M_LITE and KIT_T2G_C-2D-6M-DDR_LITE.

Working assignment for the `smif_core` personality, including drive modes. The SMIF signals are
fixed-function device pins, so this applies to **KIT_T2G_C-2D-6M_LITE and
KIT_T2G_C-2D-6M-DDR_LITE** alike — they carry the same `MXSMIF_V4` block on the same device
family. What differs between the two is the slot layout and the PSRAM XIP base, not the pins.
Read the pins back from the project's `design.modus` or `cycfg_pins.c` before relying on them.

| Signal | Pin | Drive mode | BSP alias |
| --- | --- | --- | --- |
| `spihb_clk` | P24.1 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_CLK_P` |
| `spihb_data0` | P25.0 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA0` |
| `spihb_data1` | P25.3 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA1` |
| `spihb_data2` | P23.1 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA2` |
| `spihb_data3` | P23.2 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA3` |
| `spihb_data4` | P23.0 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA4` |
| `spihb_data5` | P23.3 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA5` |
| `spihb_data6` | P25.1 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA6` |
| `spihb_data7` | P25.4 | `CY_GPIO_DM_STRONG` | `CYBSP_QSPI_DATA7` |
| `spihb_rwds` | P23.4 | `CY_GPIO_DM_PULLUP` | `CYBSP_QSPI_RWDS` |
| `spihb_select0` | P25.2 | `CY_GPIO_DM_PULLUP` | `CYBSP_QSPI_SEL0` |
| `spihb_select1` | P25.5 | `CY_GPIO_DM_PULLUP` | `CYBSP_QSPI_SEL1` (2nd device only) |

Which signals are required:

| Signal | When it is required |
| --- | --- |
| `spihb_clk` | always |
| `spihb_data0` … `data3` | quad SPI |
| `spihb_data0` … `data7` | octal SPI |
| `spihb_select0` | always — one per chip select in use (`select1` for a second device) |
| `spihb_rwds` | any DDR mode. Octal DDR parts such as the S28HS512T need this data strobe |

On KIT_T2G_B-H-16M_LITE the fixed board pins are quad-only (no RWDS): SCK P6.3, SS P6.5,
D0-D3 P7.1-P7.4, D4 P7.5, D5-D7 P8.0-P8.2.

## HAL flavour per board — which SMIF library can build

The HAL asset the BSP pulls decides which SMIF library can build. The legacy `serial-flash`
library needs `mtb-hal-cat1`, because `cy_serial_flash_qspi.h` includes `cyhal.h` and
`cy_serial_flash_qspi_init()` takes `cyhal_gpio_t` pins. The pinned `serial-memory`
`release-v2.0.0` needs a device-specific `mtb-hal-<device>`, because its header includes
`mtb_hal.h` and `mtb_serial_memory_setup()` takes a `const mtb_hal_clock_t*`. Confirm from
`libs/*.mtb` / `deps/*.mtb` in the actual project rather than from this table.

| Board | HAL asset | HAL header | Usable libraries |
| --- | --- | --- | --- |
| KIT_T2G-B-H_LITE | `mtb-hal-cat1` | `cyhal.h` | `serial-flash` only |
| KIT_T2G-B-H_LITE | `mtb-hal-t2gbh8m` | `mtb_hal.h` | `serial-memory` only |
| KIT_T2G-B-H_EVK | `mtb-hal-cat1` | `cyhal.h` | `serial-flash` only |
| KIT_T2G-B-H_EVK | `mtb-hal-t2gbh8m` | `mtb_hal.h` | `serial-memory` only |
| KIT_T2G_B-H-16M_LITE | `mtb-hal-t2gbh16m` | `mtb_hal.h` | `serial-memory` only |
| KIT_T2G_C-2D-4M_LITE | `mtb-hal-t2gc2d4m` | `mtb_hal.h` | `serial-memory` only |
| KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-6M-DDR_LITE | `mtb-hal-t2gc2d6m` | `mtb_hal.h` | `serial-memory` only |

The only Infineon code example built on `serial-flash` is
`mtb-t2g-example-smif-qspi-flash-read-write`, and its README lists exactly two supported kits:
KIT_T2G-B-H_EVK and KIT_T2G-B-H_LITE. Treat `serial-flash` as confined to those two boards and
only to projects that actually use the `mtb-hal-cat1` asset.

## Custom or unlisted boards

The SMIF signals are fixed-function on dedicated device ports, so a custom board does not change
the pin group — only four things vary, and all four are discoverable:

| What varies | Where to get it |
| --- | --- |
| Memory part number | Project's `design.cyqspi`, else the schematic or the part marking (ask the user) |
| Chip select | `design.cyqspi` slot, else the schematic |
| Data select (quad / octal, which lane group) | `design.cyqspi` slot; the part number implies the maximum — see [memory-parts.md](./memory-parts.md) |
| XIP base address | The slot's `StartAddress` in `design.cyqspi` — never a constant from an example |

Everything else in this file (IP revision, personality, whether pins need routing) follows from
the device, not the board: read `DEVICE_<part>_IPBLOCKS` in the BSP's `bsp.mk` and match it
against the IP revision table above.

For RWDS-specific runtime failure signatures, see [troubleshooting.md](./troubleshooting.md).
