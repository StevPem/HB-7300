#!/usr/bin/env python3
"""Dump the IC-7300 CI-V command table directly from the decompressed main image.

The firmware's CI-V interpreter (FUN_2000b03c) is table-driven:
  - command table  @ 0x2018AA2C, 8 bytes/entry, indexed by command byte (<0x2B):
        {u8 type/base-index, ..., u32 subcommand-list-ptr @ +4}
  - subcommand list: bytes terminated by 0xFD (0xFE = wildcard/none)
  - capability table @ 0x2018AB84, 16 bytes/entry, word0 bitfield:
        bit0   = implemented
        bit1   = read/query-only
        (w>>9)  & 0x1f   = min payload length
        (w>>14) & 0x7f   = max payload length

These addresses are for firmware v1.42 (SX3765 V4.96), image base 0x20005000.
Run depack_lzss.py first to produce the decompressed image.

Usage: python3 civ_extract.py main_image_clean.bin
"""
import sys, struct

BASE = 0x20005000
CMDTAB = 0x2018AA2C
CAPTAB = 0x2018AB84

MEAN = {
    0x00: "Set frequency (transceive echo)", 0x01: "Set mode (transceive echo)",
    0x02: "Read band-edge frequencies", 0x03: "Read operating frequency",
    0x04: "Read operating mode", 0x05: "Set operating frequency", 0x06: "Set operating mode",
    0x07: "Select VFO / VFO ops", 0x08: "Select memory channel", 0x09: "Memory write",
    0x0a: "Memory -> VFO", 0x0b: "Memory clear", 0x0e: "Scan control", 0x0f: "Split / duplex",
    0x10: "Tuning step", 0x11: "Attenuator", 0x13: "Speech synthesizer",
    0x14: "Set/read levels", 0x15: "Read meters", 0x16: "Set/read functions on/off",
    0x17: "Send CW message / announce", 0x18: "Power off/on", 0x19: "Read transceiver ID",
    0x1a: "Misc (memory/IF/band-stack/data-mode/settings)", 0x1b: "Repeater tone / CTCSS/DCS",
    0x1c: "PTT (00) / antenna tuner (01) / ...", 0x1e: "User band-edge table",
    0x21: "RIT/dTX frequency & on/off", 0x25: "Read/set unselected-VFO frequency",
    0x26: "Read/set unselected-VFO mode", 0x27: "Spectrum scope waveform data & control",
    0x28: "Voice/audio (service)", 0x2a: "Extended/service",
}

def main(path):
    img = open(path, "rb").read()
    def rd(a, n): return img[a - BASE: a - BASE + n]
    def rd32(a): return struct.unpack_from("<I", img, a - BASE)[0]

    print("cmd  len    flags  subcommands                                  meaning")
    combos = 0
    for cmd in range(0x2b):
        e = CMDTAB + cmd * 8
        typ = rd(e, 1)[0]
        subptr = struct.unpack_from("<I", rd(e, 8), 4)[0]
        if typ == 0:
            continue
        subs = []
        if BASE <= subptr < BASE + len(img):
            p = subptr
            for _ in range(80):
                b = rd(p, 1)[0]; p += 1
                if b == 0xfd: break
                subs.append(b)
        w = rd32(CAPTAB + typ * 0x10)
        mn = (w >> 9) & 0x1f
        mx = (w >> 14) & 0x7f
        flags = w & 0x7f
        combos += len(subs) if subs else 1
        ss = " ".join(f"{x:02x}" for x in subs) if subs else "-"
        print(f"0x{cmd:02x} {mn:>2}..{mx:<2} 0x{flags:02x}   {ss:<44} {MEAN.get(cmd,'?')}")
    print(f"\nTotal command/subcommand combinations: {combos}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
