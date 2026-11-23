# LIN Configurator fields and failure modes

## Contents

- **Working in the tool** — layout, multi-instance, Notice List, signal operations
- **Configurator fields** — General, Frames, Signals, Transport Layer and Configuration Services
  subtabs: every field with its valid range, plus the structural limits
- **Readback map** — each agreed value and the `mtbcfg_lin.c` field that holds it
- **Bus hardware** — example parts for a transceiver, VBAT and a master; examples on the older API
- **Failure modes** — defects that survive a clean build, with the detail behind the skill's gates
- **Diagnostics without a console** — `l_ifc_read_status` bits, `l_ifc_ioctl` operations
- **Low power, sleep and wake** — what the middleware does to the pins and how to come back
- **Transport layer and configuration services** — `ld_*` API, cooked and RAW, configuration
  persistence, the Read by identifier callback
- **Reference examples** — how to fetch CE243029

The LIN Configurator regenerates `GeneratedSource/mtbcfg_lin.c/h` beside `design.mtblin` — not
under `bsps/TARGET_<bsp>/config/`, which is the opposite of the Device Configurator layout.

Instance numbering drives the macro prefix: "Slave Instance 0" produces `mtb_lin_0_config` and
`MTB_LIN_0_*`.

## Working in the tool

The window is one slave instance with five subtabs plus a **Notice List** pane along the bottom.

**Check the Notice List before every save.** It collects errors, warnings, tasks and notes from
all five subtabs in one place, and double-clicking an entry jumps to the parameter that caused
it. Most misconfigurations announce themselves here rather than at build time.

**Multi-instance is not multiple interfaces by default.** Edit → *Add new instance* creates a
second slave prefixed `MTB_LIN_1_*`. Two things make that a trap:

- The middleware **ignores the interface handle**. Instances are separated by the
  `mtb_stc_lin_context_t` you pass, not by `iii`, which the `l_ifc_*` bodies either mark
  `CY_UNUSED_PARAMETER` or hand straight on. `LIN_IFC_HANDLE` is documentation, not routing.
- Each instance needs its own SCB with a UART mux on the package. Where only one SCB has it, a
  second instance has nothing to bind to.

## General subtab

| Field | Valid values |
|-------|--------------|
| Protocol specification compatibility | LIN 2.2 with ISO 17987, or without |
| Use automatic response_error signal | on / off |
| Bus inactivity timeout detection | 4000–10000 ms |
| Break detection threshold (bit times) | 10, 11 or 12; the tool default is 11 |
| Automatic baud rate synchronization | on / off |
| Nominal LIN bus baud rate | 1000–20000 baud; list offers 2400, 9600, 10417, 19200 |

**Automatic baud rate synchronization** — keep it on. Disabling it is an option only when the
slave clock stays within 1.5 % of nominal; from there up to 14 % it is what makes the node work
at all, and past 14 % nothing does. Either way the node must hold 2 % against the master after
the sync byte.

**Checksum** — not configurable. The middleware computes the enhanced checksum for ordinary
frames and the classic checksum for diagnostic frames automatically, per LIN 2.x. Do not look for
a setting.

**Open LDF/NCF file** lives on this tab, and importing replaces manual frame and signal entry.
Exporting an NCF writes a node capability file describing this slave as the bus sees it — hand it
to whoever integrates the cluster. The configuration file's own import and export sit in the
window header, reachable from any tab.

## Frames subtab

Toolbar: **Add**, **Delete**, **Up/Down**. Diagnostic frames are not shown here.

| Column | Meaning and limits |
|--------|--------------------|
| Index | Ordering only, not editable |
| Name | Unique. **Becomes the macro suffix** |
| Default ID | `0x00`–`0x3B`, hex. The master may reassign IDs at run time |
| Direction | **Publish** (slave transmits) or **Subscribe** (slave receives) |
| Length | 1–8 bytes |
| Type | Unconditional or Event-triggered |
| Association | Links an event-triggered frame to one unconditional frame |

Structural limits: at most **60 frames**, **256 bytes** across all frames.

Event-triggered rules: a Subscribe frame cannot be event-triggered; an event-triggered frame
needs at least one associated unconditional frame; the association is one-to-one, so a frame
already associated disappears from the other rows' choices. Deleting a frame moves its signals
back to **Unplaced Signals** rather than deleting them.

## Signals subtab

Signals are placed onto frames by drag and drop between the **Unplaced Signals** pane and the
**Frames and Signal Relations** pane. Double-clicking a signal opens **Signal Properties**.

| Property | Valid values |
|----------|--------------|
| Attribute | Read-only: `User signal`, or `Response error` for the RE signal |
| ID | Ordering number, not editable |
| Name | Letters, digits and underscores only |
| Type | **Scalar** (1–16 bits) or **Byte array** (1–8 bytes) |
| Length | Follows the type |
| Initial value | Entered in **decimal** in the GUI |
| Position | Start bit on the frame, 0–63 |

The **Legend** pane lists every signal with its position, owning frame and warnings — use it to
confirm placement before saving.

Toolbar: *Clone signal* warns when the copy keeps the same name — duplicate names mean duplicate
macro suffixes. *Move signal to unplaced* detaches without deleting. *Renumber signals' IDs*
leaves names, and therefore macro names, untouched.

## Transport Layer subtab

Segments messages longer than 8 bytes over two reserved diagnostic frame IDs that never appear
on the Frames subtab: **MRF `0x3C`** (master → slave) and **SRF `0x3D`** (slave → master).

**When you need it.** Only if the master runs a diagnostic session against this node — reading
fault memory, running a service routine, flashing. A node that only exchanges signals does not
need it. Choose Cooked unless the cluster needs frame-level control.

| Field | Valid values |
|-------|--------------|
| Use Transport Layer | on / off |
| API format | Cooked (one call per message) or RAW (one call per frame) |
| Initial NAD | Slave node address; may change at run time |
| Maximum message length | 6–4095 bytes |
| TX / RX queue length | 8–2048 bytes in 8-byte steps, RAW format only |

## Configuration Services subtab

**What it is for.** These let the master reconfigure a slave *at run time* over the diagnostic
frames, instead of every node being fixed at build time. Typically: nodes sharing a NAD are given
unique ones during commissioning with `0xB0` or `0xB3`; or the OEM assigns frame IDs at
production rather than in firmware (`0xB7`, with `0xB2` to confirm the part first).

`0xB3` discriminates on any identifier the node answers, restricted to Ids 0–31 — in practice the
LIN Product Identification or the serial number, since 2–31 are reserved. Nodes sharing a NAD and
a Product ID can therefore still be separated by serial number. What neither service separates is
nodes identical in **all** of those: they need instance generation (the initial NAD list in the
NCF), distinct initial addressing such as strapping pins feeding `ld_set_configuration`, physical
isolation during commissioning, or an instance-discovery mechanism such as SNPD, which `0xB5`
does not provide here.

**When you need it.** Enable them when the cluster specification says the master uses them.
"This cluster does not use them" is not the same as "the node need not support them" — LIN 2.2A
requires a slave to support `0xB2` with identifier 0 and `0xB7`.

**Use Transport Layer** gates the subtab: it must be on to enable **Automatic Configuration
Request Handling**, which in turn enables the per-service checkboxes. Even then the middleware
answers only five requests — `0xB0`, `0xB2`, `0xB3`, `0xB6` and `0xB7` — and only those ticked.

Requests not handled automatically reach the application through the Transport Layer API. This includes 
all requests when automatic handling is disabled, any of the five supported automatic services that are 
individually disabled, and 0xB1, 0xB4, and 0xB5, which have no automatic handlers.

| Service | Note |
|---------|------|
| `0xB0` Assign NAD | optional |
| `0xB1` Assign frame identifier | obsolete |
| `0xB2` Read by identifier | mandatory for identifier 0 |
| `0xB3` Conditional change NAD | optional |
| `0xB4` Data dump | optional |
| `0xB5` Assign NAD via SNPD | **reserved** in LIN 2.2A; the name is the middleware's |
| `0xB6` Save configuration | optional |
| `0xB7` Assign frame identifier range | mandatory |

Slave identification — `Supplier ID` `0x0000`–`0x7FFE`, `Function ID` `0x0000`–`0xFFFE`,
`Variant` `0x00`–`0xFF`. The ranges stop one short because `0x7FFF` and `0xFFFF` are the
wildcards a master uses to address any node. Always ask the user for the real values from their
cluster specification. Shipping a placeholder makes two vendors' nodes answer
`Read by identifier` identically.

---

# Readback map

Each value agreed in the LIN Configurator and where `GeneratedSource/mtbcfg_lin.c` holds it. Two
fields are re-encoded and will look wrong if compared naively:

| Agreed in the LIN Configurator | Field in `mtbcfg_lin.c` |
|---|---|
| Baud rate, auto-sync | `.baud_rate`, `.auto_baud_rate_sync` |
| Compatibility | `.spec`, `.iso17987` |
| Frame ID | ⚠ `.initial_pid` — the **PID**, not the ID entered: ID `0x10` → `0x50`, `0x11` → `0x11`, `0x12` → `0x92` |
| Frame direction | `.direction` — `MTB_LIN_FRAME_DIR_PUBLISH` / `_SUBSCRIBE` |
| Frame length | `.size`, in **bytes** |
| Signal placement | `.frame_index`, `.bit_offset` |
| Signal type and length | `.type`; ⚠ `.size` in **bits** — an 8-byte array reads `64U` |
| Inactivity timeout | `.inactivity_enabled`, `.inactivity_threshold` in ms |
| Break threshold | `.break_threshold` |
| Node address | `.initial_nad` |
| Diagnostic transport | `.tl_enabled`, `.tl_api_format` |
| Run-time reconfiguration | `.auto_config_request_handling`, the `.service_*` flags |
| Node identification | `.supplier_id`, `.function_id`, `.variant` |

A frame yields a flag handle only. A signal yields a flag handle for **each placement**, but
signals sharing a name across frames share a **single** signal handle — which is why
`mtbcfg_lin.c` carries `.num_of_signals` and `.num_of_signal_handles` as separate counts.

---

# Bus hardware

When a code example found for the board pins `lin` at `latest-v1.X` (check its dependencies in
`describe_code_example.py` output), reuse only its hardware setup — the code uses the older API.

Ways to meet the four requirements — **examples, not required parts**:

| Requirement | Examples |
|---|---|
| Transceiver | a CAN and LIN shield such as CY8CKIT-026; a third-party transceiver board |
| VBAT | a 12 V bench supply or adapter on the transceiver board's power input; an analyser that outputs VBAT on its LIN connector |
| Bus partner | an analyser in master mode, such as PCAN-USB Pro FD or the Silicon Engines LIN-USB 9011; another board running a LIN master |

---

# Failure modes

## 1. A debug console needs a second UART-capable SCB

Run the UART-mux grep from step 2 of the skill: it lists every SCB that has a UART RX and TX on
this package. Drop the LIN SCB, then check `cycfg_pins.h` and `cycfg_peripherals.h` for which of
the remaining SCBs and pins are already taken. If one is free, retarget-io may use it.

If none is, tell the user that LIN and a UART console cannot both be routed on this part, and let
them choose: report state with LEDs or over the LIN bus itself, move LIN to another SCB if that
frees a UART, or give up the console. Do not free an SCB the project already uses without asking.

## 2. Names entered in the GUI are the ABI

Re-read `GeneratedSource/mtbcfg_lin.h` after any configurator session: a rename silently breaks
every reference in the application. Passing a frame handle to a signal accessor will not compile
against the generated header — the cheap way to catch the mix-up.

## 3. The middleware owns the clock divider

The configurator displays `baud = HFClk / divider / 16`. That describes the result; it is not an
instruction. At init the middleware reads HFClk with `Cy_SysClk_ClkHfGetFrequency()`, computes
the divider from the configured baud rate and programs it itself, so a working project can show a
divider of 1.

What matters is **HFClk**: the middleware requires `baud × 16 <= HFClk`, then checks the
achievable rate against a tolerance and fails init if the error is too large. That tolerance is
far tighter with automatic baud rate synchronization **disabled** than enabled.

If `l_sys_init` or `l_ifc_init` fails on a correctly wired board, suspect HFClk first, and
prefer leaving auto-synchronization on.

## 4. Enabling `response_error` is only half the step

The unplaced-signal error exits `1` and writes no files. A frame left with no signals at all fails
the same way. The middleware maintains the signal once placed; do not write it from the
application.

## 5. Tool version

Configurations written by LIN Configurator 1.80 open and re-save cleanly in 2.0 — same file format
version, placement preserved. 2.0's updated default signal placement applies to newly created
content, not to an imported configuration. After an upgrade, still confirm the Legend.

## 6. A transceiver enable pin, on boards that have one

When frames are generated and the master still sees silence, check that pin's **initial state**
before anything else: at `0` the SCB transmits perfectly and the transceiver never passes a bit
to the bus. Fix it in the Device Configurator — do not reach for `Cy_GPIO_*` in the application.

## 7. SysTick started before the middleware

Enabling SysTick in the Device Configurator's clock tree has `cybsp_init()` start it before
`l_ifc_init` runs. The middleware then accepts the running timer at whatever period it has, with
no error, and the inactivity timeout fires at the wrong time.

---

# Diagnostics without a console

Where the package has no second UART for a console (failure mode 1), these two calls are the
substitute — read them and signal the result with an LED or over the bus. With a console, print
them.

## `l_ifc_read_status`

Returns `l_u16`, and **clears the flags as it reads them** — calling it twice does not give the
same answer.

| Bits | Meaning |
|------|---------|
| `[15:8]` | Last received PID |
| `[6]` | Save Configuration |
| `[5]` | Event-triggered frame collision — always `0` in a slave |
| `[4]` | Bus Activity |
| `[3]` | Go To Sleep |
| `[2]` | Overrun |
| `[1]` | Successful Transfer |
| `[0]` | Error in Response |

Reading it against the symptom:

| Observation | Likely cause |
|-------------|--------------|
| Bus Activity `0` | the master is not sending headers, the transceiver has no VBAT, or its enable pin is low |
| Bus Activity `1`, Successful Transfer `0` | traffic exists but this node never answers — wrong frame IDs or directions |
| Error in Response | checksum or length mismatch against the master |
| Overrun | two or more frames were processed since the previous call — read more often, or expect it when polling slowly |
| Last received PID | which frame the master last addressed; blink it out to confirm the node is being polled |

## `l_ifc_ioctl`

| Operation | Use |
|-----------|-----|
| `MTB_LIN_IOCTL_READ_STATUS` | the status word above |
| `MTB_LIN_IOCTL_SYNC_COUNTS` | sync-field timer counts — with auto baud sync on, this is the master's **measured** rate |
| `MTB_LIN_IOCTL_GET_FRAME_PID` / `SET_FRAME_PID` | inspect or override a frame PID at run time |
| `MTB_LIN_IOCTL_GET_NAD` / `SET_NAD` | node address |
| `MTB_LIN_IOCTL_SET_BAUD_RATE` | change rate after init |
| `MTB_LIN_IOCTL_SET_SERIAL_NUMBER` | serial number for identification services |
| `MTB_LIN_IOCTL_STS_BUS_INACTIVITY` / `STS_TARGET_RESET` | inactivity and reset status |
| `MTB_LIN_IOCTL_SLEEP` / `WAKEUP` | low power — see below |

`SYNC_COUNTS` is the closest thing to a bus monitor available without extra hardware: it tells
you what rate the node actually measured, which separates "wrong baud" from "wrong frame IDs".

None of this replaces a LIN master or a bus analyser. Confirming the wire still needs one.

---

# Low power, sleep and wake

`MTB_LIN_IOCTL_SLEEP` prepares the interface for a low-power mode. It disables the interrupt,
disables and de-initialises the UART, disables the clock divider, and switches the **TX pin to
`CY_GPIO_DM_ANALOG`** (high impedance).

The **RX pin is deliberately left as it is** — that is the whole wake-up mechanism: any node
driving the line dominant is seen on RX.

`MTB_LIN_IOCTL_WAKEUP` restores TX to `CY_GPIO_DM_STRONG_IN_OFF` and re-runs `l_ifc_init`. If
that init fails it puts TX back to analog and returns `MTB_LIN_STATUS_IFC_IOCTL_WAKEUP`, so the
return value must be checked — a failed wake leaves the node off the bus.

Waking the bus is not the master's privilege: `l_ifc_wake_up()` makes this slave transmit the
dominant wake-up pulse itself. It sends **one** pulse — repeating it is the application's job.
LIN 2.2A wants another attempt if no break arrives within 150–250 ms, and a pause of at least
1.5 s after three.

Sleep is entered on the master's go-to-sleep command or after the bus inactivity timeout — which
is why failure mode 7 matters: a wrong SysTick period moves that timeout.

---

# Transport layer and configuration services

The skill body covers the calls that make a working slave node. These two areas are the rest of
the slave-side surface, switched on from the LIN Configurator subtabs of the same name. The
signatures below follow LIN 2.2A and `mtb_shared/lin/latest-v2.X` — confirm them there before
writing code.

## Transport layer

`ld_init(LIN_IFC_HANDLE, &gl_lin_context)` must run before any other `ld_*` call, and again to
reset the layer. It does not abort a diagnostic frame already on the bus.

The API format chosen in the subtab decides which pair of calls applies. Mixing them is not
supported.

**Cooked** — the middleware segments and reassembles:

```c
ld_send_message   (l_ifc_handle iii, l_u16 length, l_u8 nad, const l_u8* ld_data, ctx);
ld_receive_message(l_ifc_handle iii, l_u16* length, l_u8* nad, l_u8* ld_data, ctx);
l_u8 ld_tx_status(l_ifc_handle iii, ctx);
l_u8 ld_rx_status(l_ifc_handle iii, ctx);
```

`nad` is **not used in a slave node** — the message goes to the master whatever you pass. Do not
call `ld_receive_message` again until `ld_rx_status` reports `LD_COMPLETED`, or the returned
length and data may be inconsistent.

**RAW** — eight bytes at a time; the application does the segmentation, and the TX/RX queue
lengths from the subtab are what it queues into:

```c
ld_put_raw(l_ifc_handle iii, const l_u8* ld_data, ctx);   /* 8 bytes */
ld_get_raw(l_ifc_handle iii, l_u8* ld_data, ctx);         /* 8 bytes */
l_u8 ld_raw_tx_status(l_ifc_handle iii, ctx);
l_u8 ld_raw_rx_status(l_ifc_handle iii, ctx);
```

Neither transfer is complete when the call returns — poll the matching status until it leaves
`LD_IN_PROGRESS`:

| Status | Meaning |
|---|---|
| `LD_IN_PROGRESS` / `LD_COMPLETED` / `LD_FAILED` | cooked transfer state |
| `LD_N_AS_TIMEOUT` | from `ld_tx_status` — the response was never polled off this node |
| `LD_N_CR_TIMEOUT` | from `ld_rx_status` — the master stopped mid-message |
| `LD_WRONG_SN` | sequence number error in a segmented message |
| `LD_QUEUE_EMPTY` / `LD_QUEUE_AVAILABLE` / `LD_QUEUE_FULL` | RAW queue state |
| `LD_NO_DATA` / `LD_DATA_AVAILABLE` | nothing received / a message is waiting |
| `LD_TRANSMIT_ERROR` / `LD_RECEIVE_ERROR` | bus-level failure |

## Configuration services

With **Automatic Configuration Request Handling** on, the `mtb_lin_service_*` functions are
called from `mtb_lin_ld.c`, never from the application. Whatever the middleware does not answer
arrives through the transport layer for the application to handle — see the Configuration
Services subtab for which requests those are.

With auto-handling on, the application has exactly two jobs.

**1. Persist the configuration.** The middleware changes NAD and PIDs in RAM only. When the
master sends Save Configuration, bit `[6]` of `l_ifc_read_status` is set; that is the signal to
write them to flash:

```c
/* NAD followed by one PID per frame. LIN_CFG_FRAMES is the application's own
   constant; the run-time count is in mtb_lin_0_config.num_of_frames, and the
   configurator caps a design at 60 frames. */
l_u8 cfg[1U + LIN_CFG_FRAMES];
l_u8 len = sizeof(cfg);

if (LD_READ_OK == ld_read_configuration(LIN_IFC_HANDLE, cfg, &len, &gl_lin_context))
{
    /* write cfg[0..len-1] to NVM */
}
```

The bytes are the current NAD followed by the current PIDs, in the order the frames appear in the
LDF or NCF. `ld_read_configuration` returns `LD_LENGTH_TOO_SHORT` if the buffer is too small.

Restore at start-up **after `l_ifc_init`** — `ld_set_configuration` puts nothing on the bus:

```c
(void)l_ifc_init(LIN_IFC_HANDLE, &CYBSP_LIN_ifc_config, &gl_lin_context);
ld_set_configuration(LIN_IFC_HANDLE, saved_cfg, saved_len, &gl_lin_context);
```

It returns `LD_SET_OK`, `LD_LENGTH_NOT_CORRECT` or `LD_DATA_ERROR`. The same call is how a node
takes an initial NAD from strapping pins.

**2. Answer user-defined Read by identifier.** The middleware handles the standard identifiers;
IDs `32`–`63` are the supplier's own and reach a callback the application registers:

```c
static l_u8 read_by_id_cb(l_ifc_handle iii, l_u8 id, l_u8* frame_data, l_u8* data_length);

mtb_lin_register_read_by_id_callback(read_by_id_cb, &gl_lin_context);
```

Return `LD_POSITIVE_RESPONSE` after filling `frame_data` and `data_length`,
`LD_NEGATIVE_RESPONSE` to reject the identifier, or `LD_NO_RESPONSE` to stay silent.

---

# Reference examples

`mtb-example-ce243029-lin-slave` (CE243029) is the verified example
behind this skill. It declares one dependency — `lin (latest-v2.X)` — and sets no Makefile
`COMPONENTS`. It is a **reference, not a starting template**. Reach for it when a question cannot
be settled from this skill — the exact call order, what the ISRs contain, how the flag loop is
structured:

```
python .github/skills/mtb-tools/scripts/describe_code_example.py mtb-example-ce243029-lin-slave
python .github/skills/mtb-tools/scripts/describe_code_example.py mtb-example-ce243029-lin-slave --source
python .github/skills/mtb-tools/scripts/describe_code_example.py mtb-example-ce243029-lin-slave --read main.c
```

Its `main.c` is the authority on call order. Its frame IDs, baud rate and supplier IDs are **not**
authoritative for anyone else's cluster — see the baseline table in the skill.
