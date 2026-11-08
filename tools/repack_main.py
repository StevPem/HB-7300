#!/usr/bin/env python3
"""Extract or rebuild the IC-7300 MAIN-CPU image inside a firmware .dat — the full repack chain.

The MAIN image is LZSS-compressed at file offset 0x1002C (flash 0x18010000), inside container
section 0; the fonts/resources that share section 0 begin at 0x210000 and must be preserved.
Rebuilding recompresses the modified MAIN image, writes it back (0xFF-padded to 0x210000 so the
section length is unchanged), and re-seals section 0's MD5 — producing a .dat the updater accepts.
There is no signature (see docs/modding-feasibility.md), so this is sufficient.

Verified end-to-end: extract -> modify -> rebuild yields a .dat whose section-0 MD5 is valid and
whose MAIN image decodes to the modified bytes, with all other sections byte-identical.

Usage:
  python3 repack_main.py extract firmware.dat main.bin
  python3 repack_main.py rebuild firmware.dat main.bin out.dat     # main.bin = your modified image

!! Flashing a bad image can brick the radio (see docs/flash-driver.md). Test on a backup, keep the
   original, and understand the recovery/dual-image path first. RF-compliance is your responsibility.
"""
import sys, struct, hashlib
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from pack_lzss import compress, decompress

MAIN_OFF = 0x1002C      # LZSS main image (size word + stream) inside section 0
RES_OFF  = 0x210000     # fonts/resources inside section 0 — preserve

def hdr0(d):            # section-0 (MAIN flash image) length
    return struct.unpack_from('<I', d, 0x10)[0]

def extract(dat_path, out_path):
    d = open(dat_path, 'rb').read()
    main = decompress(d[MAIN_OFF:])
    open(out_path, 'wb').write(main)
    print(f"extracted MAIN image: {len(main)} bytes -> {out_path}")

def rebuild(dat_path, main_path, out_path):
    d = bytearray(open(dat_path, 'rb').read())
    main = open(main_path, 'rb').read()
    exp = struct.unpack_from('<I', d, MAIN_OFF)[0]
    if len(main) != exp:
        print(f"WARNING: main image length {len(main)} != original {exp}; the decompressor uses the "
              f"size word, so a different length is fine as long as it's intended.")
    comp = compress(main)
    assert decompress(comp) == main, "internal round-trip failed"
    if MAIN_OFF + len(comp) > RES_OFF:
        sys.exit(f"ERROR: recompressed MAIN ({len(comp)}) + offset exceeds resource region 0x{RES_OFF:x}; "
                 f"won't fit without relocating resources.")
    # write compressed MAIN, 0xFF-pad up to the resource region (keeps section-0 length constant)
    d[MAIN_OFF:RES_OFF] = comp + b'\xff' * (RES_OFF - MAIN_OFF - len(comp))
    # re-seal section 0 MD5
    L = hdr0(d)
    d[0x2C + L:0x2C + L + 16] = hashlib.md5(bytes(d[0x2C:0x2C + L])).digest()
    open(out_path, 'wb').write(d)
    # self-verify
    ok_md5 = hashlib.md5(bytes(d[0x2C:0x2C + L])).digest() == bytes(d[0x2C + L:0x2C + L + 16])
    ok_dec = decompress(bytes(d[MAIN_OFF:])) == main
    print(f"rebuilt: MAIN {len(main)} -> {len(comp)} compressed; section-0 MD5 {'OK' if ok_md5 else 'FAIL'}; "
          f"decodes to modified image {'OK' if ok_dec else 'FAIL'} -> {out_path}")
    if not (ok_md5 and ok_dec):
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 5 and sys.argv[1] == 'rebuild':
        rebuild(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__); sys.exit(1)
