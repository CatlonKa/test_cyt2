---
name: mtb-scb-lin-slave
description: "Use when adding, configuring or troubleshooting a LIN slave node built on an SCB: setting up a LIN cluster, importing an LDF or NCF, defining frames and signals, binding LIN to an SCB in Device Configurator, wiring a LIN transceiver and master for testing, checking the generated mtbcfg_lin.c/h, or writing code with the l_* LIN API. Also use when the LIN master gets no response from the node. Supports LIN slave nodes only, not masters."
license: "Apache-2.0"
metadata:
  author: "Infineon ModusToolbox Team"
  version: "1.0.0"
---

# LIN Slave over SCB

A LIN node here is the **LIN middleware** driving an **SCB** in UART mode, plus a **LIN
transceiver** between the SCB pins and the bus. Three software layers must agree, and the
generated symbols are the contract between them:

| Layer | Tool | Produces |
|-------|------|----------|
| Hardware binding | Device Configurator → `design.modus` | `<ALIAS>_ifc_config` |
| Protocol | **LIN Configurator** → `design.mtblin` | `mtb_lin_0_config`, `MTB_LIN_0_*` handles |
| Application | Your code | ISRs, init, flag loop |

## When to Use

- A node has to answer frame headers from an existing LIN cluster
- A cluster specification or LDF has to become a working slave node
- LIN is configured but the master sees nothing on the bus

### When Not to Use

- **The user needs a LIN master.** This middleware implements a slave node only.

## Key Files

| File | Purpose |
|------|---------|
| `bsps/TARGET_<bsp>/config/design.modus` | `lin-slave` personality on an SCB, and the transceiver enable pin where the board has one — Device Configurator only |
| `design.mtblin` (**project root**) | frames, signals, baud — LIN Configurator only |
| `GeneratedSource/mtbcfg_lin.c/h` | `mtb_lin_0_config` and the `MTB_LIN_0_*` handles — generated, never hand-edited |
| `bsps/TARGET_<bsp>/config/GeneratedSource/cycfg_peripherals.h` | `<ALIAS>_ifc_config`, or `scb_<n>_ifc_config` when no alias was set |
| `deps/lin.mtb` | library reference — presence confirms installation |
| `mtb_shared/lin/<version>/` | middleware source — the authority on function signatures |

## Quick Reference

| Item | Value |
|------|-------|
| **Hardware** | any SCB whose UART RX/TX mux reaches the pins wired to the transceiver |
| **Library** | `lin` middleware v2.x (core name `mtb-lin`) |
| **Devices** | the series listed in `mtb_shared/lin/<version>/README.md` |
| **Bus** | a LIN transceiver, its supply (VBAT) and a bus partner — see [Bus hardware](#bus-hardware) |

## ⛔ Gates (read first)

| # | Gate | Violation |
|---|------|-----------|
| G0 | **Both configurators are GUI-only** — you instruct, the user clicks. Never edit `design.modus`, `design.mtblin` or `GeneratedSource/mtbcfg_lin.*` | Writing XML into a config file |
| G1 | **Slave only** — if asked for a LIN master, say plainly the middleware provides a slave node, and stop | Presenting master frame scheduling as achievable |
| G2 | **A console needs a second UART-capable SCB** — before offering retarget-io or `printf`, check which other SCBs have a UART mux on this package and are free. If none is, tell the user LIN and a console cannot both be routed and let them choose | Offering a debug UART on an SCB that has no UART mux on this package, or silently dropping the console |
| G3 | **Names are the ABI** — each frame/signal name becomes a macro suffix verbatim | Using a handle name never entered in the GUI |
| G4 | **`response_error` needs placing** — the General checkbox only adds an unplaced "RE" signal; it must be dragged onto a publish frame, or generation fails with `Signal 'Response_Error' is not placed on a frame` | Assuming the checkbox alone reports errors |
| G5 | **Never set the SCB clock divider** — the middleware computes and programs it at `l_ifc_init` from HFClk (`Cy_SysClk_ClkHfGetFrequency()`). Gate on HFClk instead | Calling `Cy_SysClk_Periph*Divider()` to fix the baud rate |
| G6 | **Both ISRs are mandatory** — `l_ifc_rx` for traffic, `l_ifc_aux` for the inactivity timer | Registering only the RX ISR |
| G7 | **Verify from the generated files, not the GUI** — `mtbcfg_lin.h` defines the handles, `mtbcfg_lin.c` holds the entire configuration. Read both before writing code | Writing `MTB_LIN_0_*` from memory, or asking the user to re-read the configurator for something the generated file already states |
| G8 | **Establish the cluster before configuring** — the master owns baud rate, frame IDs, directions and lengths. Ask for the LDF, or ask the questions in step 3. Offer defaults to confirm, never as facts | Copying the example's 19200 baud and `0x10`/`0x11` frame IDs into a cluster that uses different ones |
| G9 | **Leave SysTick to the middleware** — `l_ifc_init` registers the inactivity handler on SysTick and, if the timer is not already running, starts it at **1 ms**. The inactivity threshold is counted in those ticks, so any other period silently moves the timeout | Enabling SysTick in the Device Configurator's clock tree, calling `Cy_SysTick_Init` or `Cy_SysTick_Enable` from application code, or letting an RTOS own SysTick at a tick rate other than 1 ms |

## Bus hardware

The SCB produces logic-level UART only. On the bus a LIN node also needs a **transceiver**, its
**supply** and a **bus partner** that sends frame headers; check whether the board carries a
transceiver at all.

**Say this to the user at the start:** the node can be configured and built without any bus
hardware — enough to learn the tools — but proving it works needs a LIN transceiver (for example
the CY8CKIT-026 CAN and LIN Shield Kit, or any equivalent) and a LIN master or analyser. When the
user wants to test, establish the four points below. Never connect the LIN wire (VBAT, commonly
12 V) to an MCU pin.

| Question | What to establish |
|---|---|
| Is a transceiver on the board? | From the kit user guide or schematic. If not, one has to be added |
| How do its lines reach the SCB? | Transceiver RXD → SCB UART RX pin, TXD → SCB UART TX pin, and its enable/sleep input (often `NSLP` or `EN`) → a GPIO, or tied high in hardware |
| What supplies it? | VBAT, commonly 12 V — a bench supply, the shield's power input, or a master/analyser that provides VBAT on its LIN connector |
| What is the bus partner? | A LIN master node, or an analyser acting as master, at the cluster's baud rate |

**Read the LIN code example READMEs, even when they name another kit.** Find LIN examples with the
`mtb-list-code-examples` skill, take the GitHub URL that `describe_code_example.py` prints, and
read the **Supported kits** and **Hardware setup** sections. The hardware setup shows how a
transceiver, its enable input, VBAT and the master are connected; that arrangement carries over to
any board. Only the pin numbers are board-specific: take them from the README if it lists the
user's kit, otherwise from the kit user guide, and confirm them against the SCB UART mux (step 2).
Example parts and examples on the older API:
[lin-reference.md — Bus hardware](./references/lin-reference.md#bus-hardware).

**Transceiver enable pin.** Where the board drives the transceiver's enable or sleep input from a
GPIO, configure that pin **declaratively** in Device Configurator — no application code drives it:

| Setting | Value |
|---------|-------|
| Personality | **Pin** |
| Alias | `LIN_NSLP` by convention |
| Drive mode | `CY_GPIO_DM_STRONG_IN_OFF` |
| Initial state | **`1`** — this is what holds the transceiver awake from `cybsp_init()` |

Where the enable input is tied high in hardware there is no such pin, and its absence is not a
fault.

## Workflow

**1. Add the middleware.** Install the `lin` library at `latest-v2.X`; confirm `deps/lin.mtb` and
`mtb_shared/lin/`. If an existing project pins `latest-v1.X`, the API differs from this skill —
say so before writing code. Nothing else in the build changes — no `COMPONENTS`, `DEFINES`,
`SOURCES` or `INCLUDES` edits.

**2. Device Configurator — bind LIN to an SCB.** Instruct the user; do not edit the file.

Pick the SCB from the pins first. The board decides which pins reach the transceiver; the SCB is
whichever instance has a UART RX and TX mux on those pins. Find the candidates in the
`gpio_<die>_<package>.h` that the project's device header includes, under `mtb_shared/`:

```
grep -E "P[0-9]+_[0-9]+_SCB[0-9]+_UART_(RX|TX)" gpio_<die>_<package>.h
```

Check `cycfg_pins.h` and `cycfg_peripherals.h` that the pins and the SCB are not already used. A pin
that carries only BSP aliases is wired to something on the board (an LED, a touch electrode, a
header); tell the user what before using it. Then present the settings:

| Setting | Value |
|---------|-------|
| Peripheral | `scb[<n>]` from the check above → personality **LIN-1.0** (stored as `lin-slave` in `design.modus`) |
| Alias | `CYBSP_LIN` — if left unset the generated struct is `scb_<n>_ifc_config`; use whatever name the config actually produced |
| Interrupt Priority | **`1`** — the personality default `3` is the lowest priority when the device header sets `__NVIC_PRIO_BITS` to `2`, and at the lowest priority the node loses bytes under load; nothing in the build or a bus-less bench shows it |
| Clock | a **16-bit** peripheral divider that **nothing else uses** — the middleware supports no other type and rewrites the divider value at `l_ifc_init`, which silently re-clocks any other block on the same divider (typically a debug UART) |
| RX / TX | the pins the board routes to the transceiver |

Add the transceiver enable pin from [Bus hardware](#bus-hardware) where the board has one.

Once the settings are on the table, launch the tool.
Run: `python .github/skills/mtb-tools/scripts/run_tool.py config`

**3. LIN Configurator — ask about the cluster, then configure it.**

The master owns the schedule, so the cluster — not this example — decides almost every value in
this tool.

**First ask whether an LDF or NCF exists.** If the OEM supplied one, import it — frames, signals,
IDs and names all come out matching the cluster specification, and the rest of this step is done.

Without an LDF, take whichever branch fits: ask the questions below when the user is integrating
into an existing cluster, or start from the baseline further down when they are exploring LIN.
Valid ranges for every answer are in the reference's General, Frames and Signals subtab tables.

- Which master or cluster spec? Can you share its project, LDF or config file? — that settles
  baud, frame IDs, directions and lengths at once
- Nominal baud rate?
- LIN 2.2 with or without ISO 17987? — changes configuration-service behaviour
- Which frame IDs will the master address to this node?
- For each frame: **Publish = this slave transmits**, Subscribe = it receives — state it from the
  slave's side, this is the most common mix-up
- How many bytes in each frame, and where does each signal sit inside it?
- Does the master read node identification? — only then do Supplier/Function/Variant matter
- Does the master use diagnostic transport or reassign NADs at run time? — decides the Transport
  Layer and Configuration Services subtabs
- Does the cluster sleep, and after how long? — sets the inactivity timeout

**If the user has no master yet and no cluster spec**, do not interrogate them. Start from the
configuration of CE243029 (`design.mtblin` in that example), say plainly that it is a starting
point, and name what will have to change once a real master appears:

| Setting | CE baseline | Revisit when a master exists? |
|---------|-------------|-------------------------------|
| Compatibility | LIN 2.2 without ISO 17987 | yes, if the cluster specifies ISO 17987 |
| Baud rate | 19200, auto-sync on | **yes — must match the cluster exactly** |
| Inactivity timeout | 7000 ms | rarely — a per-node setting, not a cluster-wide value |
| Break detection threshold | 12 bit times | yes — LIN 2.2A specifies 11 |
| Frames | `InFrame` `0x10` Subscribe 8 B · `OutFrame` `0x11` Publish 8 B · `ErrorSignalFrame` `0x12` Publish 8 B | **yes — IDs, directions and lengths are cluster-owned** |
| Signals | `SignalInput` and `SignalOutput` byte arrays of 8 B · `Response_Error` 1 bit | **yes — layout must match the cluster** |
| Transport layer | off | yes, if the master uses diagnostics |
| Configuration services | off | yes, if the master reassigns NAD or frame IDs |
| Supplier / Function ID | `0x7FFE` / `0x4841` | **yes — placeholders, not your IDs.** Editable only with Transport Layer on; otherwise they stay `0x0000`, which is fine unless the master reads node identification |

Never present the baseline as if it were the user's cluster. Keep **automatic baud rate
synchronization** on, and state up front that the **checksum model is not configurable** — both
are explained under General subtab in the reference.

Launch: Device Configurator → LIN SCB → **External Tools → LIN Configurator** (opens
`design.mtblin` in the project root; **Ctrl+S** saves it there). Fallback:
`python .github/skills/mtb-tools/scripts/run_tool.py lin-configurator`.
Full field tables and valid ranges: [lin-reference.md](./references/lin-reference.md).

**4. Generate the configuration code, then verify it.**

`GeneratedSource/mtbcfg_lin.c/h` are produced two ways, so they are normally current: saving in
the LIN Configurator writes them, and `make build` regenerates them as well — `mtbninja --generate`
runs `lin-configurator-cli` as a code generator before compiling. A `mtbcfg_lin.timestamp`
sentinel records the tool version.

This is also where a broken configuration surfaces. The generator names the object it rejected —
`Frame 'X' of the Unconditional type does not contain any signals`, or the G4 message — so relay
that message; it points straight at the field to fix.

⛔ **Successful generation does not mean a correct configuration.** The generator does not
range-check the baud rate and does not reject duplicate frame IDs (it silently moves another frame
to `0x00`). Only the readback below catches these.

Then read `GeneratedSource/mtbcfg_lin.h` and list the handles it actually defines before writing
code (G7). Names map straight through:

| Configurator entry | Generated macro |
|--------------------|-----------------|
| Frame `InFrame` | `MTB_LIN_0_FLAG_HANDLE_InFrame` |
| Signal `SignalInput` | `MTB_LIN_0_SIGNAL_HANDLE_SignalInput` **and** `MTB_LIN_0_FLAG_HANDLE_SignalInput` |

**Then read `mtbcfg_lin.c` and check it against what step 3 agreed.** It is generated C, so the
whole configuration is machine-readable — do not send the user back to the GUI to confirm any of
it. Field-by-field map, including the two re-encoded fields (frame ID as PID, signal size in
bits): [lin-reference.md — Readback map](./references/lin-reference.md#readback-map).

Step 2 is machine-readable too — check `cycfg_peripherals.c` for `CYBSP_LIN_ifc_config`, or
`scb_<n>_ifc_config` when no alias was set:

| Agreed in step 2 | Field |
|---|---|
| Interrupt priority | `.intr_priority` — `3UL` means the personality default was left in place |
| SCB instance | `.scb_base` — must be the `SCB<n>` chosen in step 2 |
| TX pin | `.tx_port`, `.tx_pin` — must be the pin the board routes to the transceiver |
| Clock divider | `.divider_num` — no other `Cy_SysClk_PeriphAssignDivider()` call in `cycfg_peripherals.c` may use the same divider |
| Enable pin | `<ALIAS>_DRIVEMODE` = `CY_GPIO_DM_STRONG_IN_OFF` and `<ALIAS>_INIT_DRIVESTATE` = `1` in `cycfg_pins.h` |

Report any field that disagrees and have the user correct it in the configurator, then
regenerate. **This check is only as good as its reference, and there are two of them:** the LDF or
cluster specification settles the LIN protocol values, while the SCB instance, TX pin and
interrupt priority are whatever step 2 agreed for this board. Where the agreed values are not
known — a configuration made in an earlier session, say — ask for the missing reference rather
than treating the generated files as correct because they compile.

**5. Write the application** — see the next section.

**6. Build, then verify on the bus.** Run:

```
python .github/skills/mtb-tools/scripts/run_make.py --args build
```

A clean build proves nothing here: every trap in this skill compiles. Confirm on the wire with a
LIN master or an analyser through a transceiver ([Bus hardware](#bus-hardware)); without them,
say plainly that the node is built but not verified. A console, where one exists (G2), shows what
the node did, not what reached the bus. Drive an LED from the subscribe flag so reception is
observable.

If the master sees silence, walk the checks in order — transceiver supply and wiring, the
transceiver enable pin's initial state where the board has one, then the handles in
`mtbcfg_lin.h`, then HFClk. The last three are in [lin-reference.md](./references/lin-reference.md).

## Middleware API

Standard LIN `l_*` calls. Verify any name not listed here against `mtb_shared/lin/*/` before
using it — do not guess.

```c
#define LIN_IFC_HANDLE  (0u)            /* matches "Slave Instance 0" */
mtb_stc_lin_context_t gl_lin_context;

static void LIN_Isr(void)           { l_ifc_rx (LIN_IFC_HANDLE, &gl_lin_context); }
static void LIN_InactivityIsr(void) { l_ifc_aux(LIN_IFC_HANDLE, &gl_lin_context); }

if (MTB_LIN_STATUS_SUCCESS != l_sys_init(&mtb_lin_0_config, &gl_lin_context,
                                         &LIN_Isr, &LIN_InactivityIsr)) { handle_error(); }
if (l_ifc_init(LIN_IFC_HANDLE, &CYBSP_LIN_ifc_config, &gl_lin_context))  { handle_error(); }
```

Both config structs must be present to link.

| Call | Purpose |
|------|---------|
| `l_ifc_rx` / `l_ifc_aux` | the two mandatory ISR bodies |
| `l_ifc_init`, `l_ifc_read_status`, `l_ifc_wake_up` | interface control |
| `l_flg_tst` / `l_flg_clr` | test and clear a frame or signal flag |
| `l_bytes_rd` / `l_bytes_wr` | Byte array signals — `(sss, start_byte, count, pData, context)` |
| `l_bool_rd/_wr`, `l_u8_rd/_wr`, `l_u16_rd/_wr` | Scalar signals, matched to bit length |

Match the accessor to the signal **Type** chosen in the configurator.

```c
for (;;)
{
    if (l_flg_tst(MTB_LIN_0_FLAG_HANDLE_InFrame, &gl_lin_context))
    {
        l_bytes_rd(MTB_LIN_0_SIGNAL_HANDLE_SignalInput, 0u, 8u, rx_buf, &gl_lin_context);
        l_flg_clr(MTB_LIN_0_FLAG_HANDLE_InFrame, &gl_lin_context);
    }
    l_bytes_wr(MTB_LIN_0_SIGNAL_HANDLE_SignalOutput, 0u, 8u, tx_buf, &gl_lin_context);
}
```

Clear a flag only after consuming the data it announces. Writing a publish signal does not
transmit — the master owns the schedule; the slave keeps its response buffer current for
whenever the frame header arrives.

## Reference

[lin-reference.md](./references/lin-reference.md) — every configurator field with its valid range,
the `mtbcfg_lin.c` readback map, example bus hardware parts, failure modes that survive a clean
build, console-less diagnostics, sleep/wake, and the transport layer and configuration services
APIs.
