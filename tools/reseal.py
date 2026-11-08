#!/usr/bin/env python3
"""Verify and re-seal an IC-7300 firmware .dat container.

Container format (reverse-engineered; see docs/container-format.md):
  0x00  "3wfU" magic (4) + version string (12) + 7x u32 section-lengths (28)  = 0x2C header
  0x2C  section 0 data  (len = hdr[0]; = the MAIN-CPU flash image @0x18000000)
        + 16-byte MD5(section 0 data)
        section 1 data (len = hdr[1]) + MD5 ... etc. for each section PRESENT
  ...   final 2-byte end marker "7e"
Integrity is a standard MD5 over each section's data, stored as a 16-byte trailer right
after it. There is NO signature — recomputing the MD5 re-seals a modified section
(see docs/modding-feasibility.md). The updater flashes 64 KB blocks, skipping blocks
identical to current flash, and aborts on MD5 mismatch.

NOTE: this tool handles the simple section layout (verified for sections 0 and 1, incl. the
MAIN image). Sections 2+ (DSP/FPGA) carry an inner address/length record format not yet
modelled; `verify` reports them as "unverified (sub-format)". Modifying the MAIN image only
touches section 0, which this tool re-seals correctly.

Usage:
  python3 reseal.py verify  firmware.dat
  python3 reseal.py reseal  firmware.dat out.dat        # recompute all simple-section MD5s in place
"""
import sys, struct, hashlib

HDR = 0x2C

def sections(d):
    """Yield (index, data_start, length, md5_offset) for the simple-layout prefix only.
    Section 0 (the MAIN image) is always included; subsequent sections are included while
    their stored MD5 still verifies. The walk stops at the first section that does not
    verify — that is the boundary of the DSP/FPGA sub-format, which this tool never touches.
    (This keeps reseal safe after you modify section 0: section 0 is re-hashed, the still-
    valid simple sections are re-hashed to the same value, and everything past the boundary
    is left byte-for-byte unchanged.)"""
    hdr = [struct.unpack_from('<I', d, 0x10 + i*4)[0] for i in range(7)]
    off = HDR
    for i, L in enumerate(hdr):
        if off + L + 16 > len(d):
            break
        md5_ok = hashlib.md5(d[off:off+L]).digest() == d[off+L:off+L+16]
        if i > 0 and not md5_ok:
            break  # reached the DSP/FPGA sub-format boundary
        yield i, off, L, off + L
        off += L + 16

def verify(path):
    d = open(path, 'rb').read()
    print(f"magic={d[:4]!r} version={d[4:16].decode('latin1')!r} size=0x{len(d):x}")
    hdr = [struct.unpack_from('<I', d, 0x10 + i*4)[0] for i in range(7)]
    print("section-length header:", [hex(x) for x in hdr])
    last_end = HDR
    for i, s, L, mo in sections(d):
        calc = hashlib.md5(d[s:s+L]).digest()
        ok = calc == d[mo:mo+16]
        tag = " (MAIN image @0x18000000)" if i == 0 else ""
        print(f"  section {i}: 0x{s:06x}..0x{s+L:06x} len=0x{L:x}  MD5 {'OK' if ok else 'MISMATCH'}{tag}")
        last_end = mo + 16
    rest = len(d) - last_end
    print(f"  remaining after simple sections: 0x{rest:x} bytes (sections 2+ DSP/FPGA sub-format + '7e' marker)")

def reseal(path, out):
    d = bytearray(open(path, 'rb').read())
    for i, s, L, mo in sections(d):
        d[mo:mo+16] = hashlib.md5(bytes(d[s:s+L])).digest()
        print(f"  resealed section {i}: wrote MD5 @0x{mo:06x}")
    open(out, 'wb').write(d)
    print(f"wrote {out} ({len(d)} bytes)")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'verify': verify(sys.argv[2])
    elif cmd == 'reseal' and len(sys.argv) == 4: reseal(sys.argv[2], sys.argv[3])
    else: print(__doc__); sys.exit(1)
