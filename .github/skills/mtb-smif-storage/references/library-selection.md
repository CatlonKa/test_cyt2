# Library selection and project wiring

Contents:

- terms used by the skill
- key files to inspect
- detect which SMIF library the project uses
- decision rules
- pin `serial-memory` to `release-v2.0.0`
- build configuration changes

Use this file when deciding which SMIF library the project uses and when updating build wiring
for that choice.

## Terms used in this skill

| Term | What it means in a project |
| --- | --- |
| `cyhal` HAL | The `mtb-hal-cat1` asset, which provides `cyhal.h` and `cyhal_*` types |
| `mtb_hal` HAL | A device-specific `mtb-hal-<device>` asset (`mtb-hal-t2gbh8m`, `mtb-hal-t2gbh16m`, `mtb-hal-t2gc2d4m`, `mtb-hal-t2gc2d6m`, ...), which provides `mtb_hal.h` and `mtb_hal_*` types, and no `cyhal.h` |
| `serial-memory` | Current SMIF library, `mtb_serial_memory_*` API, flash and PSRAM |
| `serial-flash` | Legacy SMIF library, `cy_serial_flash_qspi_*` API, NOR flash only, requires `cyhal` (`mtb-hal-cat1`) |

When talking to the user, name the HAL by its asset and header (`mtb-hal-cat1` / `cyhal.h`, or
`mtb-hal-<device>` / `mtb_hal.h`), not by generation labels.

## Key files to inspect

| File / directory | Purpose |
| --- | --- |
| `deps/serial-memory.mtb` | Current library reference |
| `deps/serial-flash.mtb` | Legacy library reference |
| `../mtb_shared/serial-memory/<version>/include/mtb_serial_memory.h` | Current library header with the exact installed signatures |
| `../mtb_shared/serial-flash/<version>/cy_serial_flash_qspi.h` | Legacy library header |
| `bsps/TARGET_<bsp>/config/design.modus` | Device Configurator source |
| `bsps/TARGET_<bsp>/config/design.cyqspi` | QSPI Configurator source |
| `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_peripherals.c/h` | Generated SMIF peripheral symbols and HAL clock assignment |
| `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_qspi_memslot.c/h` | Generated memory-slot and block symbols |
| `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_system.c/h` | Generated system clock path and frequencies |
| `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_routing.h` | Generated signal routing |
| `templates/TARGET_<bsp>/config/design.cyqspi` | App-level override, if the application uses one |
| `Makefile` | `DEFINES` for thread safety and XIP programming |

## Detect which SMIF library the project uses

Collect all of the following signals from the project. Do not stop at the first one; a mismatch
between signals is itself useful information.

1. List `deps/*.mtb` and, on older projects, `libs/*.mtb`.
2. Search the sources for `mtb_serial_memory.h` and `cy_serial_flash_qspi.h`.
3. Search the sources for `mtb_serial_memory_` and `cy_serial_flash_qspi_`.
4. Search the project for the HAL flavour: `mtb_hal.h` / `mtb-hal-<device>` / `COMPONENTS=... MTB_HAL`
   versus `cyhal.h` / `mtb-hal-cat1`.
5. Read `GeneratedSource/cycfg_qspi_memslot.h` to learn the generated block-config symbols used by
   this board and SMIF instance.

`deps/` is the authoritative signal. Do not treat `../mtb_shared/` as evidence of what the
project uses; it is a workspace cache shared by other applications.

| Signal | Current path: `serial-memory` | Legacy path: `serial-flash` |
| --- | --- | --- |
| Dependency file | `deps/serial-memory.mtb` | `deps/serial-flash.mtb` |
| Header | `mtb_serial_memory.h` | `cy_serial_flash_qspi.h` |
| API prefix | `mtb_serial_memory_*` | `cy_serial_flash_qspi_*` |
| HAL requirement | `mtb_hal` (`mtb-hal-<device>`) for this pinned `serial-memory` `release-v2.0.0` flow | `cyhal` (`mtb-hal-cat1`) only |
| Who initializes SMIF | application: `Cy_SMIF_Init()` + `Cy_SMIF_Enable()` + `mtb_serial_memory_setup()` | library: `cy_serial_flash_qspi_init()` |
| PSRAM support | yes | no |

Both libraries consume the same QSPI Configurator output.

## Decision rules

- One library clearly present: use it and report the evidence.
- Both present in `deps/`: stop and ask the user which one to keep, then remove the other.
- Neither present: default to `serial-memory` on `mtb_hal` (`mtb-hal-<device>`) projects.

For this skill's SMIF flow, require `serial-memory` `release-v2.0.0`; newer releases are not
supported for this SMIF bring-up flow. See
[Pin serial-memory to release-v2.0.0](#pin-serial-memory-to-release-v200).

`serial-memory` `release-v2.0.0` requires the `mtb_hal` HAL: its header includes `mtb_hal.h`,
and `mtb_serial_memory_setup()` takes a `const mtb_hal_clock_t*`. If the project only has
`mtb-hal-cat1` (`cyhal.h`) and the user explicitly wants to stay there, keep or choose the legacy
`serial-flash` path instead of forcing `serial-memory`.

Only stay on `serial-flash` when the project already uses it, or when the user explicitly wants
the legacy API on an `mtb-hal-cat1` BSP. For HAL and board restrictions on that path, read
[legacy-api.md](./legacy-api.md).

## Pin serial-memory to release-v2.0.0

1. Read `deps/serial-memory.mtb`. The pinned form is a single line:

   ```text
   https://github.com/cypresssemiconductorco/serial-memory/#release-v2.0.0#$$ASSET_REPO$$/serial-memory/release-v2.0.0
   ```

   The release appears twice: after the first `#` (the Git tag) and at the end of the path.
2. If the file is missing, or either occurrence is a different release (for example
   `release-v3.2.0` or `latest-v3.X`), offer one of these to the user:
   - edit `deps/serial-memory.mtb` to the line above, or
   - open Library Manager, select `serial-memory` for this project, set the version to
     `release-v2.0.0`, and click Update.
3. Run `make getlibs` in the project directory.
4. Confirm `../mtb_shared/serial-memory/release-v2.0.0/include/mtb_serial_memory.h` exists and
   use that header for every signature check. `mtb_shared/serial-memory/` may also contain other
   releases used by other applications in the workspace; ignore them.

## Build configuration changes

Edit the `Makefile` of the project that owns the SMIF block:

- `serial-memory`, RTOS project: add `DEFINES+=MTB_SERIAL_MEMORY_THREAD_SAFE`.
- `serial-memory`, external-memory programming from the toolchain: add
  `DEFINES+=MTB_SERIAL_MEMORY_ENABLE_XIP_PROGRAM`.
- Confirm `deps/serial-memory.mtb` is pinned to `release-v2.0.0` (or `deps/serial-flash.mtb`
  is present for the legacy path) and that `make getlibs` has been run.

If `MTB_SERIAL_MEMORY_THREAD_SAFE` is needed, also confirm the project has the
`abstraction-rtos` dependency.