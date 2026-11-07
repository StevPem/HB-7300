#!/usr/bin/env python3
"""Depack an Icom IC-7300 (Renesas RZ/A1) LZSS firmware image.

Algorithm recovered from the stage-2 loader at runtime addr 0x2000425C:
  Okumura LZSS, ring buffer N=4096 (init 0x00, write index starts at 0xFEE),
  flag byte LSB-first (1=literal, 0=match),
  match = 2 bytes B0,B1: offset = B0 | ((B1 & 0xF0) << 4)  (12-bit),
                         length = (B1 & 0x0F) + 3          (3..18).
The source word at `src_off` is the uncompressed length; the stream follows.

Usage: python3 depack_lzss.py <firmware.dat> <src_off (e.g. 0x1002c)> <out.bin>
"""
import sys, struct

def depack(data, src_off):
    out_size = struct.unpack_from('<I', data, src_off)[0]
    sp = src_off + 4
    N = 0x1000
    ring = bytearray(N)
    r = 0xFEE
    out = bytearray()
    flags = 0
    while len(out) < out_size and sp < len(data):
        flags >>= 1
        if not (flags & 0x100):          # reload flag byte, 0xFF00 marks 8 valid bits
            flags = data[sp] | 0xFF00
            sp += 1
        if flags & 1:                    # literal
            c = data[sp]; sp += 1
            out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
        else:                            # back-reference
            b0 = data[sp]; b1 = data[sp + 1]; sp += 2
            offset = b0 | ((b1 & 0xF0) << 4)
            length = (b1 & 0x0F) + 3
            for i in range(length):
                c = ring[(offset + i) & 0xFFF]
                out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
                if len(out) >= out_size:
                    break
    return out, out_size, sp - (src_off + 4)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    data = open(sys.argv[1], 'rb').read()
    src = int(sys.argv[2], 0)
    out, declared, consumed = depack(data, src)
    open(sys.argv[3], 'wb').write(out)
    print(f"declared size=0x{declared:x} produced={len(out)} consumed={consumed} -> {sys.argv[3]}")
