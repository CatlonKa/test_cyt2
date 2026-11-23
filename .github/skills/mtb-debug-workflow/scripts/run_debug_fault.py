#!/usr/bin/env python3
"""Skill: run_debug_fault
Orchestrates fault capture via the ModusToolbox MCP 'debug_run_gdb_script' tool.

This script handles:
1. Selecting the GDB script for the target core: generic Cortex-M by default,
   PSE84 TrustZone/CM55 scripts only when the project is a PSE84 target
2. Calling the MCP tool (which handles OpenOCD/GDB lifecycle and per-core GDB port)
3. Parsing raw GDB output into structured sections
4. PSE84 CM33 only: running reset-and-catch when TrustZone cleared the fault registers

Usage:
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core <core> [options]

Examples:
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core cm7
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core cm4
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core cm0p
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core cm33 --cwd proj_cm33_ns
    python .github/skills/mtb-debug-workflow/scripts/run_debug_fault.py --target-core cm55 --cwd proj_cm55
"""

import sys
import os
import re
import json
import argparse
from datetime import datetime

# Add mtb-tools/scripts to path for mtbskill
current_dir = os.path.dirname(os.path.abspath(__file__))
skills_dir = os.path.dirname(os.path.dirname(current_dir))  # up to skills/
tools_dir = os.path.join(skills_dir, "mtb-tools", "scripts")
sys.path.insert(0, tools_dir)

from mtbskill import bootstrap_skill  # type: ignore

SCRIPTS_DIR = os.path.join(current_dir, "gdb-scripts")  # current_dir is the scripts/ dir

# Must stay in sync with the target_core values accepted by debug_run_gdb_script.
SUPPORTED_CORES = ["cm0p", "cm4", "cm7", "cm7_0", "cm7_1", "cm7_2", "cm7_3", "cm33", "cm55"]
ARMV6M_CORES = {"cm0p"}  # no CFSR/HFSR/MMFAR/BFAR
PSE84_CORES = {"cm33", "cm55"}

# KitProg3 test-mode acquire resets the device on connect, which destroys the fault state.
# PSOC 4 OpenOCD configs use their own variable name.
NO_ACQUIRE_VARS = {"ENABLE_ACQUIRE": "0", "PSOC4_USE_ACQUIRE": "0"}

# Extra seconds the MCP client waits beyond the tool's own timeout_seconds.
MCP_TIMEOUT_MARGIN = 30

CFSR_BITS = {
    0: "MemManage: IACCVIOL (instruction access violation)",
    1: "MemManage: DACCVIOL (data access violation)",
    3: "MemManage: MUNSTKERR (fault while unstacking on exception return)",
    4: "MemManage: MSTKERR (fault while stacking on exception entry)",
    5: "MemManage: MLSPERR (fault during FPU lazy state preservation)",
    8: "BusFault: IBUSERR (instruction fetch bus error)",
    9: "BusFault: PRECISERR (precise data bus error; stacked PC is the faulting instruction)",
    10: "BusFault: IMPRECISERR (imprecise data bus error; stacked PC is after the faulting store)",
    11: "BusFault: UNSTKERR (bus fault while unstacking on exception return)",
    12: "BusFault: STKERR (bus fault while stacking on exception entry)",
    13: "BusFault: LSPERR (bus fault during FPU lazy state preservation)",
    16: "UsageFault: UNDEFINSTR (undefined instruction)",
    17: "UsageFault: INVSTATE (invalid state, e.g. branch to an address with the Thumb bit clear)",
    18: "UsageFault: INVPC (invalid EXC_RETURN on exception return)",
    19: "UsageFault: NOCP (coprocessor/FPU access while disabled)",
    20: "UsageFault: STKOF (stack limit overflow, ARMv8-M)",
    24: "UsageFault: UNALIGNED (unaligned access with UNALIGN_TRP set)",
    25: "UsageFault: DIVBYZERO (integer divide by zero with DIV_0_TRP set)",
}
CFSR_MMARVALID = 1 << 7
CFSR_BFARVALID = 1 << 15
HFSR_BITS = {
    1: "HardFault: VECTTBL (bus fault on vector table read)",
    30: "HardFault: FORCED (escalated from a configurable fault)",
    31: "HardFault: DEBUGEVT (debug event)",
}
EXCEPTION_NAMES = {2: "NMI", 3: "HardFault", 4: "MemManage", 5: "BusFault", 6: "UsageFault",
                   7: "SecureFault", 11: "SVCall", 12: "DebugMonitor", 14: "PendSV", 15: "SysTick"}
FAULT_EXCEPTIONS = {3, 4, 5, 6, 7}

SOURCE_EXTS = (".c", ".h", ".cpp", ".hpp", ".s", ".S")
SKIP_DIRS = {"build", "libs", ".git", ".github", ".vscode", "mtb_shared"}

SECTION_RE = re.compile(r"^=== (.+?) ===[ \t]*$", re.MULTILINE)
REGISTER_RE = re.compile(r"^(\w+)\s+(0x[0-9a-fA-F]+)", re.MULTILINE)
PRINTF_VALUE_RE = re.compile(r"^([A-Za-z_]+):\s*0x([0-9a-fA-F]+)\s*$", re.MULTILINE)
X_VALUE_RE = re.compile(r"^([A-Za-z_]+)[^\n]*:\s*\n0x[0-9a-fA-F]+[^:\n]*:\s*0x([0-9a-fA-F]+)", re.MULTILINE)
LINE_RE = re.compile(r'Line (\d+) of "([^"]+)"(?:.*?<([^>]+)>)?')
NO_LINE_RE = re.compile(r"No line number information available for address (0x[0-9a-fA-F]+)(?: <([^>]+)>)?")
GDB_ERROR_RE = re.compile(r"Error in sourced command file:\s*\n(.+)")
# '#3  0x0000019c in main () at C:/ws/main.c:121' or '#4  0x10000000 in cy_m0p_image ()'
FRAME_RE = re.compile(r"^#\d+\s+(?:(0x[0-9a-fA-F]+) in )?(\S+) \(.*\)(?: at (.+):(\d+))?\s*$")


def workspace_root() -> str:
    """Workspace root in the deployed layout (<root>/.github/skills/<skill>/scripts), else the CWD."""
    agent_dir = os.path.dirname(skills_dir)
    if os.path.basename(skills_dir) == "skills" and os.path.basename(agent_dir).startswith("."):
        return os.path.dirname(agent_dir)
    return os.getcwd()


def detect_pse84(project_dir: str):
    """True/False if the project's openocd.tcl or BSP names a PSE84 target, None if neither was found.

    Looks in the same places the MCP server does: openocd.tcl in the project dir,
    bsps/ in the project dir or its parent (multi-core sub-projects).
    """
    evidence = []
    tcl = os.path.join(project_dir, "openocd.tcl")
    if os.path.isfile(tcl):
        try:
            with open(tcl, encoding="utf-8", errors="ignore") as f:
                evidence.append(f.read())
        except OSError:
            pass
    for bsps in (os.path.join(project_dir, "bsps"), os.path.join(os.path.dirname(project_dir), "bsps")):
        if os.path.isdir(bsps):
            evidence.extend(os.listdir(bsps))
            break
    if not evidence:
        return None
    return any(re.search(r"pse84|cat1d\.", e, re.IGNORECASE) for e in evidence)


def select_gdb_script(target_core: str, pse84: bool) -> tuple:
    """Return (script path, profile name) for a core.

    - pse84-cm33-trustzone: PSE84 CM33, reads Secure + Non-Secure SCB (reset-and-catch capable)
    - pse84-cm55: PSE84 CM55
    - generic-armv6m: CM0+ (no CFSR/HFSR, reads ICSR + stacked frame)
    - generic: any other Cortex-M (CM4, CM7, CM33/CM55 outside PSE84)
    """
    if pse84 and target_core == "cm33":
        return os.path.join(SCRIPTS_DIR, "fault-capture-cm33-trustzone.gdb"), "pse84-cm33-trustzone"
    if pse84 and target_core == "cm55":
        return os.path.join(SCRIPTS_DIR, "fault-capture-cm55.gdb"), "pse84-cm55"
    if target_core in ARMV6M_CORES:
        return os.path.join(SCRIPTS_DIR, "fault-capture-armv6m.gdb"), "generic-armv6m"
    return os.path.join(SCRIPTS_DIR, "fault-capture-default.gdb"), "generic"


def extract_section(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between markers from GDB output."""
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    nl = text.find("\n", start)
    if nl >= 0:
        start = nl + 1
    end = text.find(end_marker, start)
    if end == -1:
        return text[start:].strip()
    return text[start:end].strip()


def fault_regs_all_zero(fault_regs: str) -> bool:
    """Check if all fault register values are 0x00000000."""
    if not fault_regs:
        return True
    hex_values = re.findall(r"0x([0-9a-fA-F]{8})", fault_regs)
    if not hex_values:
        return True
    # Skip values that are addresses (before the colon)
    # Only check values after :\t or :\s patterns
    value_lines = re.findall(r":\s*0x([0-9a-fA-F]{8})", fault_regs)
    if not value_lines:
        return True
    return all(v == "00000000" for v in value_lines)


def parse_sections(raw: str) -> dict:
    """Map each '=== Name ===' header in the GDB output to the text that follows it."""
    matches = list(SECTION_RE.finditer(raw))
    sections = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        sections[m.group(1)] = raw[m.end():end].strip()
    return sections


def section_text(sections: dict, prefix: str) -> str:
    return "\n".join(text for name, text in sections.items() if name.startswith(prefix))


def parse_values(text: str) -> dict:
    """Register values printed as 'NAME: 0x..' (printf) or 'NAME ...:' + 'x/1xw' output."""
    values = {name: int(v, 16) for name, v in X_VALUE_RE.findall(text)}
    values.update({name: int(v, 16) for name, v in PRINTF_VALUE_RE.findall(text)})
    return values


def exception_name(number: int) -> str:
    if number >= 16:
        return f"IRQ {number - 16}"
    return EXCEPTION_NAMES.get(number, f"exception {number}")


def decode_fault_status(values: dict) -> tuple:
    """Return (fault_type list, fault_address) from CFSR/HFSR/ICSR values, including _S/_NS copies."""
    fault_type, fault_address = [], ""
    for label, value in values.items():
        base, _, bank = label.partition("_")
        suffix = f"_{bank}" if bank else ""
        tag = f" [{bank}]" if bank else ""
        if base == "CFSR":
            fault_type += [name + tag for bit, name in CFSR_BITS.items() if value >> bit & 1]
            if value & CFSR_BFARVALID and "BFAR" + suffix in values:
                fault_address = f"0x{values['BFAR' + suffix]:08x} (BFAR{suffix})"
            elif value & CFSR_MMARVALID and "MMFAR" + suffix in values:
                fault_address = f"0x{values['MMFAR' + suffix]:08x} (MMFAR{suffix})"
        elif base == "HFSR":
            fault_type += [name + tag for bit, name in HFSR_BITS.items() if value >> bit & 1]
        elif base == "ICSR" and value & 0x1FF:
            fault_type.append(f"Active exception: {exception_name(value & 0x1FF)} (ICSR.VECTACTIVE)")
    return fault_type, fault_address


def display_path(path: str, root: str) -> str:
    """Path relative to the workspace root when inside it, with '/' separators."""
    try:
        rel = os.path.relpath(path, root)
        path = path if rel.startswith("..") else rel
    except ValueError:
        pass
    return path.replace(os.sep, "/")


def parse_info_line(text: str, root: str) -> str:
    """Turn GDB 'info line' output into 'file:line (function+offset)' or 'address (no source line)'."""
    m = LINE_RE.search(text)
    if m:
        where = f" ({m.group(3)})" if m.group(3) else ""
        return f"{display_path(m.group(2), root)}:{m.group(1)}{where}"
    m = NO_LINE_RE.search(text)
    if m:
        where = f", in {m.group(2)}" if m.group(2) else ""
        return f"{m.group(1)} (no source line{where})"
    return ""


def backtrace_fault_frames(backtrace: str, root: str) -> tuple:
    """(fault, caller) locations from the frames GDB unwound below '<signal handler called>'."""
    lines = backtrace.splitlines()
    marker = next((i for i, line in enumerate(lines) if "<signal handler called>" in line), None)
    if marker is None:
        return "", ""
    locations = []
    for line in lines[marker + 1:]:
        m = FRAME_RE.match(line.strip())
        if not m:
            continue
        address, function, path, number = m.groups()
        if path:
            locations.append(f"{display_path(path, root)}:{number} ({function})")
        else:
            locations.append(f"{address or ''} (no source line, in {function})".lstrip())
        if len(locations) == 2:
            break
    locations += ["", ""]
    return locations[0], locations[1]


def stale_source(elf_path: str, project_dir: str) -> str:
    """Return a source file modified after the ELF was built, or '' if there is none."""
    try:
        elf_mtime = os.path.getmtime(elf_path)
    except OSError:
        return ""
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                if name.endswith(SOURCE_EXTS) and os.path.getmtime(path) > elf_mtime + 1:
                    return path
            except OSError:
                pass
    return ""


def analyze(raw: str, root: str) -> dict:
    """Derive fault state, decoded fault type and source locations from the GDB output."""
    sections = parse_sections(raw.replace("\r\n", "\n"))
    regs = {name.lower(): int(v, 16) for name, v in REGISTER_RE.findall(section_text(sections, "Registers"))}
    values = parse_values(section_text(sections, "Fault Status Registers"))
    fault_type, fault_address = decode_fault_status(values)
    ipsr = regs["xpsr"] & 0x1FF if "xpsr" in regs else values.get("ICSR", 0) & 0x1FF
    status_set = any(v for k, v in values.items() if k.partition("_")[0] in ("CFSR", "HFSR", "SFSR"))

    if not regs:
        state = "not_captured"
    elif ipsr in FAULT_EXCEPTIONS:
        state = "in_fault_handler"
    elif status_set:
        state = "fault_status_only"
    elif ipsr == 0:
        state = "no_fault_state"
    else:
        state = "other_exception"

    result = {
        "fault_state": state,
        "active_exception": "" if not regs else exception_name(ipsr) if ipsr else "none (thread mode)",
        "fault_type": fault_type,
        "fault_address": fault_address,
        "fault_location": parse_info_line(section_text(sections, "Fault Location"), root),
        "caller_location": parse_info_line(section_text(sections, "Caller Location"), root),
        "location_source": "stacked_frame",
        "pc_symbol": section_text(sections, "PC Symbol").partition("\n")[0],
        "pdl_fault_frame": {},
        "warnings": [],
    }

    pc = f"0x{regs['pc']:08x}" if "pc" in regs else "PC"
    if result["pc_symbol"].startswith("No symbol matches"):
        result["warnings"].append(
            f"The halted PC ({pc}) is not in the loaded ELF. The debugger may be attached to a different core "
            "than requested (check openocd_target), or this core is running other code (boot ROM, another image).")
    elif result["pc_symbol"].startswith("cy_m0p_image"):
        result["warnings"].append(
            f"The halted PC ({pc}) is inside the embedded CM0+ image, not this core's application: "
            "the debugger is probably attached to the CM0+ (check openocd_target).")

    # The live backtrace beats cy_faultFrame, which some handlers never fill (e.g. PSOC 4 startup)
    if not result["fault_location"]:
        fault, caller = backtrace_fault_frames(section_text(sections, "Backtrace"), root)
        if fault:
            result.update(fault_location=fault, caller_location=caller, location_source="backtrace")

    pdl_text = section_text(sections, "PDL Fault Frame")
    pdl_values = {k.upper(): v for k, v in parse_values(pdl_text).items()}
    if pdl_values:
        pc_part, _, lr_part = pdl_text.partition("LR location:")
        pdl_fault = parse_info_line(pc_part.partition("PC location:")[2], root)
        pdl_caller = parse_info_line(lr_part, root)
        result["pdl_fault_frame"] = {k.lower(): f"0x{v:08x}" for k, v in pdl_values.items()}
        result["pdl_fault_frame"].update({"fault_location": pdl_fault, "caller_location": pdl_caller})
        # Outside a fault handler the record is from an earlier fault (it survives resets), not this halt
        if state == "in_fault_handler" and not result["fault_location"] and pdl_values.get("PC"):
            result.update(fault_location=pdl_fault, caller_location=pdl_caller, location_source="cy_faultFrame")
            if not fault_type:
                result["fault_type"], result["fault_address"] = decode_fault_status(pdl_values)
        elif state != "in_fault_handler" and ":" in pdl_fault:
            result["warnings"].append(
                f"pdl_fault_frame records an earlier fault at {pdl_fault}. The PDL saved it before this capture "
                "and it survives resets, so it may come from a previous boot. Treat it as a lead, not as this failure.")
    if not result["fault_location"]:
        result["location_source"] = ""

    if state == "not_captured":
        result["warnings"].append(
            "GDB did not read the core registers, so nothing is known about a fault. "
            "Check error and openocd_log, then rerun.")
    elif state == "no_fault_state":
        where = result["pc_symbol"].split(" in section")[0] or pc
        result["warnings"].append(
            f"No fault is active: the core was running normal code ({where}) in thread mode and the fault status "
            "registers are clear. Either the fault has not happened yet (for example, the capture connected during "
            "a delay before the failing code), or the target was reset before capture (watchdog, a reset in the "
            "fault handler, or an OpenOCD acquire). Wait until the failure has happened and rerun.")
    elif state == "fault_status_only":
        result["warnings"].append(
            "Fault status bits are set but the core is not in a fault handler: the fault may have been "
            "handled and execution resumed.")
    return result


def build_openocd_vars(acquire: bool, extra: list) -> dict:
    """OpenOCD variables for the run: acquire off unless requested, then any --openocd-var pairs."""
    ocd_vars = {} if acquire else dict(NO_ACQUIRE_VARS)
    ocd_vars.update(dict(extra or []))
    return ocd_vars


def openocd_log_warnings(log: str, target: str = "") -> list:
    """Warnings for OpenOCD actions that changed the core state, or a core it could not reach."""
    warnings = []
    if target and (f"[{target}] Examination failed" in log or f"target {target} examination failed" in log):
        warnings.append(f"OpenOCD could not examine {target}: the core was not reachable (device in reset or deep "
                        "sleep, or the core not powered yet). Rerun; if it keeps failing, rerun with --acquire "
                        "(this resets the device, so reproduce the failure first).")
    if "acquiring device in Test Mode" in log:
        warnings.append("OpenOCD reset the device into test mode when it connected (KitProg3 acquire), so any "
                        "fault state was lost. Reproduce the failure and rerun (without --acquire if you passed it).")
    if "Clearing CPU_WAIT" in log:
        warnings.append("OpenOCD found this core waiting to be started (CPU_WAIT) and parked it in a dummy loop: "
                        "the core was not running when the debugger connected, so these registers show no fault. "
                        "Either the device was reset, or the CM33 application has not started it yet.")
    return warnings


def main():
    parser = argparse.ArgumentParser(description="Run debug fault analysis via MCP tool")
    parser.add_argument("--cwd", help="Project directory containing the built ELF")
    parser.add_argument("--config", default="Debug", choices=["Debug", "Release"])
    parser.add_argument("--target-core", choices=SUPPORTED_CORES,
                        help="Core running the faulting firmware: cm0p (PSOC 4), cm4 (PSOC 6), "
                             "cm7 = cm7_0 / cm7_1..cm7_3 (TRAVEO T2G), cm33 / cm55 (PSOC Edge E84). "
                             "Required unless the project is detected as PSE84 (defaults to cm33)")
    parser.add_argument("--profile", default="auto", choices=["auto", "generic", "pse84"],
                        help="'auto' (default) uses the PSE84 TrustZone/CM55 scripts only when openocd.tcl "
                             "or the BSP names a PSE84 target; 'generic' forces the plain Cortex-M scripts; "
                             "'pse84' forces the PSE84 scripts")
    parser.add_argument("--gdb-port", type=int, help="Override OpenOCD GDB base port (default: 3333)")
    parser.add_argument("--timeout", type=int, default=60, help="Max session time (seconds)")
    parser.add_argument("--no-reset-catch", action="store_true",
                        help="Disable automatic reset-and-catch (PSE84 CM33 TrustZone profile only)")
    parser.add_argument("--acquire", action="store_true",
                        help="Allow the KitProg3 test-mode acquire, which resets the device when OpenOCD "
                             "connects and so destroys the fault state. Use only if connecting fails without it "
                             "(e.g. device in deep sleep)")
    parser.add_argument("--openocd-var", nargs=2, action="append", metavar=("KEY", "VALUE"),
                        help="Set an OpenOCD variable before openocd.tcl is loaded; repeatable. "
                             "Example: --openocd-var DEBUG_CERTIFICATE proj_cm33_s/packets/debug_token.bin")
    parser.add_argument("--raw", action="store_true",
                        help="Include raw_output and openocd_log in the result (always included when the run fails)")
    args = parser.parse_args()

    root = workspace_root()
    project_dir = os.path.normpath(os.path.join(root, args.cwd or ""))
    if not os.path.isdir(project_dir):
        parser.error(f"Project directory not found: {project_dir}. Pass --cwd relative to the workspace root ({root})")

    detected = detect_pse84(project_dir) if args.profile == "auto" else None
    pse84 = args.profile == "pse84" or bool(detected)

    target_core = args.target_core
    if target_core is None:
        if not pse84:
            parser.error("--target-core is required for non-PSE84 targets (choose from: "
                         + ", ".join(SUPPORTED_CORES) + ")")
        target_core = "cm33"
    if pse84 and target_core not in PSE84_CORES:
        parser.error(f"PSE84 has only cm33 and cm55 cores (got --target-core {target_core}); "
                     "use --profile generic if this is not a PSE84 target")

    skill = bootstrap_skill(__file__)

    params = {
        "config": args.config,
        "target_core": target_core,
        "timeout_seconds": args.timeout,
    }
    if args.cwd:
        params["cwd"] = args.cwd
    if args.gdb_port:
        params["gdb_port"] = args.gdb_port

    script, profile = select_gdb_script(target_core, pse84)
    ocd_vars = build_openocd_vars(args.acquire, args.openocd_var)
    if ocd_vars:
        params["openocd_vars"] = ocd_vars
    params["gdb_script"] = script
    mcp_timeout = args.timeout + MCP_TIMEOUT_MARGIN
    result = skill.mcp_request("debug_run_gdb_script", timeout=mcp_timeout, **params)
    result_text = skill.mcp_text(result)

    try:
        data = json.loads(result_text)
    except json.JSONDecodeError:
        print(result_text)
        return

    # GDB output from Windows uses CRLF line endings
    raw = data.get("raw_output", "").replace("\r\n", "\n")
    target = data.get("target", "")

    # No openocd.tcl/BSP found locally: fall back to the target the server reports
    if detected is None and args.profile == "auto" and target_core in PSE84_CORES and "PSE84" in target.upper():
        script, profile = select_gdb_script(target_core, True)
        params["gdb_script"] = script
        result = skill.mcp_request("debug_run_gdb_script", timeout=mcp_timeout, **params)
        result_text = skill.mcp_text(result)
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            print(result_text)
            return
        raw = data.get("raw_output", "").replace("\r\n", "\n")

    # Extract structured sections from raw output
    backtrace = extract_section(raw, "=== Backtrace ===", "===")
    registers = extract_section(raw, "=== Registers ===", "===")
    fault_regs = extract_section(raw, "=== Fault Status Registers", "=== Done ===")

    # PSE84 CM33 TrustZone: the secure handler may clear NS fault registers before we read them
    if profile == "pse84-cm33-trustzone" and not args.no_reset_catch:
        ns_section = extract_section(raw, "Non-Secure SCB", "=== NS Exception Frame")
        if not ns_section:
            ns_section = fault_regs
        if fault_regs_all_zero(ns_section):
            print("[INFO] NS fault registers cleared by TrustZone. Running reset-and-catch...", file=sys.stderr)
            rc_script = os.path.join(SCRIPTS_DIR, "fault-capture-cm33ns-reset-catch.gdb")
            rc_params = dict(params)
            rc_params["gdb_script"] = rc_script
            # This run resets the device anyway, so keep the default acquire it was validated with
            rc_params.pop("openocd_vars", None)
            if args.openocd_var:
                rc_params["openocd_vars"] = dict(args.openocd_var)
            rc_params["timeout_seconds"] = args.timeout + 30  # Extra time for reset
            rc_result = skill.mcp_request("debug_run_gdb_script", timeout=mcp_timeout + 30, **rc_params)
            rc_text = skill.mcp_text(rc_result)
            try:
                rc_data = json.loads(rc_text)
                rc_raw = rc_data.get("raw_output", "").replace("\r\n", "\n")
                rc_fault = extract_section(rc_raw, "=== Fault Status Registers", "=== Done ===")
                if rc_fault and not fault_regs_all_zero(rc_fault):
                    # Reset-and-catch captured live registers
                    raw = rc_raw
                    backtrace = extract_section(rc_raw, "=== Backtrace ===", "===")
                    registers = extract_section(rc_raw, "=== Registers ===", "===")
                    fault_regs = rc_fault
                    data["capture_method"] = "reset_catch"
            except json.JSONDecodeError:
                pass

    analysis = analyze(raw, root)
    warnings = analysis.pop("warnings")
    if data.get("capture_method") != "reset_catch":
        warnings += openocd_log_warnings(data.get("openocd_stderr", ""), data.get("openocd_target", ""))
    if analysis["fault_state"] == "no_fault_state" and args.acquire and not any("--acquire" in w for w in warnings):
        warnings.append("--acquire resets the device when OpenOCD connects; rerun without it to keep the fault state.")
    fault_regs = section_text(parse_sections(raw), "Fault Status Registers")

    # Optional trailing sections may stop GDB early; what was captured before that is still valid.
    success = data.get("success", False)
    error = data.get("error", "")
    if not success and registers and fault_regs:
        success = True
        error = ""
        gdb_error = GDB_ERROR_RE.search(raw)
        reason = gdb_error.group(1).strip() if gdb_error else (data.get("error") or "unknown error")
        if "cy_faultFrame" in reason:
            warnings.append("This ELF has no PDL fault record (cy_faultFrame): the PDL fault handler is not "
                            "linked or CY_ARM_FAULT_DEBUG is disabled.")
        else:
            warnings.append(f"GDB stopped before the end of the script ({reason}); sections captured "
                            "before that point are valid.")

    elf_path = data.get("elf_path", "")
    elf_built = ""
    if elf_path and os.path.isfile(elf_path):
        elf_built = datetime.fromtimestamp(os.path.getmtime(elf_path)).isoformat(timespec="seconds")
        newer = stale_source(elf_path, project_dir)
        if newer:
            warnings.append(f"{os.path.relpath(newer, root)} is newer than the ELF: the board may run older "
                            "firmware than the source. Rebuild and reprogram before trusting source lines.")

    output = {
        "success": success,
        "capture_method": data.get("capture_method", "direct"),
        "fault_profile": profile,
        "gdb_script": os.path.basename(script),
        "acquire": args.acquire,
        "target": target,
        "target_core": data.get("target_core", target_core),
        "openocd_target": data.get("openocd_target", ""),
        "gdb_port": data.get("gdb_port"),
        "elf_path": elf_path,
        "elf_built": elf_built,
        **analysis,
        "warnings": warnings,
        "backtrace": backtrace,
        "registers": registers,
        "fault_regs": fault_regs,
        "error": error,
    }
    if args.raw or not success:
        output.update(raw_output=raw, openocd_log=data.get("openocd_stderr", ""))

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
