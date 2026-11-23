# Legacy API (`serial-flash`)

Contents:

- when the legacy path is valid
- HAL and board constraints
- initialization pattern
- flash access equivalents
- recommendation

Read this file only when the project uses the legacy `serial-flash` path.

## When the legacy path is valid

Use `serial-flash` only when one of the following is true:

- the project already depends on `deps/serial-flash.mtb`
- the project already contains `cy_serial_flash_qspi_*` usage the user wants to keep
- the user explicitly asks for the legacy API on an `mtb-hal-cat1` (`cyhal.h`) BSP

If neither library is present, default to `serial-memory` instead.

## HAL and board constraints

`serial-flash` works only with the `cyhal` HAL (`mtb-hal-cat1`). Its header includes `cyhal.h`,
and `cy_serial_flash_qspi_init()` takes `cyhal_gpio_t` pin arguments.

| HAL | HAL asset | Header it provides | `serial-flash` possible? |
| --- | --- | --- | --- |
| `cyhal` | `mtb-hal-cat1` | `cyhal.h` | yes |
| `mtb_hal` | `mtb-hal-<device>` — `mtb-hal-t2gbh8m`, `mtb-hal-t2gbh16m`, `mtb-hal-t2gc2d4m`, `mtb-hal-t2gc2d6m`, ... | `mtb_hal.h` only, **no `cyhal.h`** | **no** — compilation fails with `fatal error: cyhal.h: No such file or directory` |

On current T2G kits, this means:

| Board | HAL asset seen in the project | Legacy path usable? |
| --- | --- | --- |
| KIT_T2G-B-H_LITE, KIT_T2G-B-H_EVK | `mtb-hal-cat1` (`cyhal`) | yes |
| KIT_T2G-B-H_LITE, KIT_T2G-B-H_EVK | `mtb-hal-t2gbh8m` (`mtb_hal`) | no |
| KIT_T2G_B-H-16M_LITE | `mtb-hal-t2gbh16m` (`mtb_hal`) | no |
| KIT_T2G_C-2D-4M_LITE, KIT_T2G_C-2D-6M_LITE, KIT_T2G_C-2D-6M-DDR_LITE | `mtb-hal-t2gc2d4m` / `mtb-hal-t2gc2d6m` (`mtb_hal`) | no |

`serial-flash` is legacy: the only Infineon code example using it is
`mtb-t2g-example-smif-qspi-flash-read-write`, whose supported kits are exactly
KIT_T2G-B-H_LITE and KIT_T2G-B-H_EVK.

Upstream BSP metadata for `TARGET_KIT_T2G-B-H_LITE` and `TARGET_KIT_T2G-B-H_EVK` also lists
`mtb-hal-t2gbh8m`, so do not infer the HAL flavour from the board name alone; inspect the
project's `deps/` or `libs/` entries.

## Initialization pattern

The library performs the SMIF, pin and clock setup itself:

```c
#include "cyhal.h"
#include "cybsp.h"
#include "cycfg_qspi_memslot.h"
#include "cy_serial_flash_qspi.h"

cy_rslt_t result = cy_serial_flash_qspi_init(smifMemConfigs[<slot>],
                                             CYBSP_QSPI_D0, CYBSP_QSPI_D1,
                                             CYBSP_QSPI_D2, CYBSP_QSPI_D3,
                                             NC, NC, NC, NC,
                                             CYBSP_QSPI_SCK, CYBSP_QSPI_SS,
                                             QSPI_BUS_FREQUENCY_HZ);
/* handle result */
```

Use the `CYBSP_QSPI_*` pin macros the BSP actually defines; pass `NC` for the unused data lines.

## Flash access equivalents

The `serial-flash` equivalents of the current-library flash operations are:

- `cy_serial_flash_qspi_erase()`
- `cy_serial_flash_qspi_write()`
- `cy_serial_flash_qspi_read()`

This legacy path is for NOR flash only. Do not use it for PSRAM.

## Recommendation

For new projects, prefer `serial-memory` on an `mtb-hal-<device>` BSP. It supports both flash
and PSRAM, and is the default path for fresh projects.