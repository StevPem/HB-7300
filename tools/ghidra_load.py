#!/usr/bin/env python3
"""Load the IC-7300 main image into Ghidra at the correct base, with flash mapped.

Requires PyGhidra (`pip install pyghidra`) and GHIDRA_INSTALL_DIR set to a Ghidra 12.1.x
install. Loads main_image_clean.bin at RAM base 0x20005000 AND maps the raw .dat flash
at 0x18000000, so references from app code (0x20xxxxxx) to flash resources (0x182xxxxx)
resolve. After this, use the decompiler / references interactively.

Usage: GHIDRA_INSTALL_DIR=/path/to/ghidra \
       python3 ghidra_load.py main_image_clean.bin ic7300_firmware.dat
"""
import sys, pyghidra, jpype

def main(imgpath, rawpath):
    pyghidra.start()
    from ghidra.util.task import ConsoleTaskMonitor
    from java.io import ByteArrayInputStream
    with pyghidra.open_program(imgpath, project_name="ic7300",
                               project_location="ic7300_ghidra",
                               language="ARM:LE:32:v7", analyze=False) as flat:
        prog = flat.getCurrentProgram()
        sp = prog.getAddressFactory().getDefaultAddressSpace()
        tid = prog.startTransaction("setup")
        prog.setImageBase(sp.getAddress(0x20005000), True)
        raw = open(rawpath, "rb").read()[0x2c:]
        bb = jpype.JArray(jpype.JByte)(len(raw))
        for i, b in enumerate(raw):
            bb[i] = b - 256 if b > 127 else b
        prog.getMemory().createInitializedBlock(
            "flash", sp.getAddress(0x18000000),
            ByteArrayInputStream(bb), len(raw), ConsoleTaskMonitor(), False)
        prog.endTransaction(tid, True)
        flat.analyzeAll(prog)
        print("functions:", prog.getFunctionManager().getFunctionCount())
        print("base:", prog.getImageBase(), "- project saved in ./ic7300_ghidra")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2])
