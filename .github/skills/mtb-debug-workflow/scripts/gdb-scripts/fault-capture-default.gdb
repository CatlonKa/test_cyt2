# Default Cortex-M fault capture script (ARMv7-M / ARMv8-M, no TrustZone handling).
# Reads: registers, backtrace, fault status registers, the live stacked exception frame
# with its source lines, and the PDL fault record (cy_faultFrame) saved by Cy_SysLib_FaultHandler.
# The last two sections are optional: the wrapper keeps earlier results if GDB stops there.

set pagination off
set confirm off
set remotetimeout 500
set mem inaccessible-by-default off

monitor halt

echo \n=== Registers ===\n
info registers

echo \n=== PC Symbol ===\n
info symbol $pc

echo \n=== Current Frame ===\n
frame

echo \n=== Backtrace ===\n
backtrace 20

echo \n=== Fault Status Registers (ARM Cortex-M) ===\n
printf "CFSR: 0x%08x\n", *(unsigned int *)0xE000ED28
printf "HFSR: 0x%08x\n", *(unsigned int *)0xE000ED2C
printf "MMFAR: 0x%08x\n", *(unsigned int *)0xE000ED34
printf "BFAR: 0x%08x\n", *(unsigned int *)0xE000ED38
printf "SHCSR: 0x%08x\n", *(unsigned int *)0xE000ED24

echo \n=== Exception Frame (R0,R1,R2,R3,R12,LR,PC,xPSR) ===\n
# LR holds EXC_RETURN only while the handler has not called other code; bit 2 selects PSP.
if (((unsigned int)$lr & 0xFF000000) == 0xFF000000)
  if ((unsigned int)$lr & 4)
    set $efp = (unsigned int)$psp
    echo Stack: PSP\n
  else
    set $efp = (unsigned int)$msp
    echo Stack: MSP\n
  end
  x/8xw $efp
  echo \n=== Fault Location (stacked PC) ===\n
  info line *(*(unsigned int *)($efp + 24))
  echo \n=== Caller Location (stacked LR) ===\n
  info line *((*(unsigned int *)($efp + 20) & ~1) - 2)
else
  echo LR is not EXC_RETURN; use the PDL Fault Frame section.\n
end

echo \n=== PDL Fault Frame (cy_faultFrame) ===\n
printf "pc: 0x%08x\n", cy_faultFrame.pc
printf "lr: 0x%08x\n", cy_faultFrame.lr
printf "psr: 0x%08x\n", cy_faultFrame.psr
printf "cfsr: 0x%08x\n", cy_faultFrame.cfsr.cfsrReg
printf "hfsr: 0x%08x\n", cy_faultFrame.hfsr.hfsrReg
printf "mmfar: 0x%08x\n", cy_faultFrame.mmfar
printf "bfar: 0x%08x\n", cy_faultFrame.bfar
echo PC location:\n
info line *cy_faultFrame.pc
echo LR location:\n
info line *((cy_faultFrame.lr & ~1) - 2)

echo \n=== Done ===\n
quit
