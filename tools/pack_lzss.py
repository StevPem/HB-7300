#!/usr/bin/env python3
"""LZSS *compressor* matching the IC-7300 bootloader's decompressor (see depack_lzss.py).

Produces a stream the firmware's decompressor decodes back to the input:
  output = <u32 uncompressed length LE> <LZSS stream>
  stream = flag byte (LSB-first; bit=1 literal, bit=0 match), repeating every 8 tokens
  literal = 1 raw byte
  match   = 2 bytes b0,b1 with  offset = b0 | ((b1 & 0xF0) << 4)   (12-bit ring position)
                                 length = (b1 & 0x0F) + 3          (3..18)
Ring buffer N=4096 initialised to 0x00, write index starts at 0xFEE — identical to the
decoder, so a match at output index j is emitted with offset (0xFEE + j) & 0xFFF.

Any valid encoding works (the firmware only needs a correct decode), so this is a greedy
hash-chain encoder; it is NOT required to match Icom's exact bytes. Verified by round-trip
through the firmware-matching depacker.

Usage:
  python3 pack_lzss.py in.bin out.lzss          # compress (out = size word + stream)
  python3 pack_lzss.py --selftest in.bin        # compress then decompress, assert identity
"""
import sys, struct

N = 4096
F = 18
THRESHOLD = 3          # minimum match length
WINDOW = N - F         # 4078 — safe distance so long matches never read overwritten slots
MAXCHAIN = 256         # cap hash-chain search for speed

def compress(data):
    n = len(data)
    out = bytearray(struct.pack('<I', n))
    tokens = []            # list of ('lit', byte) or ('mat', offset, length)
    head = {}              # 3-byte key -> most recent position
    prev = [-1] * n        # chain of previous positions with same 3-byte key
    def key(p): return data[p] << 16 | data[p+1] << 8 | data[p+2]
    pos = 0
    while pos < n:
        best_len = 0
        best_j = -1
        if pos + 2 < n:
            k = key(pos)
            j = head.get(k, -1)
            limit = pos - WINDOW
            chain = 0
            maxlen = min(F, n - pos)
            while j >= 0 and j > limit and chain < MAXCHAIN:
                # measure match length (allow self-overlap: compare data values directly)
                L = 0
                while L < maxlen and data[j + L] == data[pos + L]:
                    L += 1
                if L > best_len:
                    best_len, best_j = L, j
                    if L == maxlen:
                        break
                j = prev[j]
                chain += 1
        if best_len >= THRESHOLD:
            offset = (0xFEE + best_j) & 0xFFF
            tokens.append(('mat', offset, best_len))
            adv = best_len
        else:
            tokens.append(('lit', data[pos]))
            adv = 1
        # insert hash entries for every position we pass (keeps chains complete)
        for p in range(pos, pos + adv):
            if p + 2 < n:
                k = key(p)
                prev[p] = head.get(k, -1)
                head[k] = p
        pos += adv
    # emit tokens in groups of 8 with a leading flag byte (LSB-first)
    i = 0
    while i < len(tokens):
        grp = tokens[i:i+8]
        flag = 0
        body = bytearray()
        for b, t in enumerate(grp):
            if t[0] == 'lit':
                flag |= (1 << b)
                body.append(t[1])
            else:
                _, offset, length = t
                body.append(offset & 0xFF)
                body.append((((offset >> 8) & 0xF) << 4) | (length - 3))
        out.append(flag)
        out += body
        i += 8
    return bytes(out)

def decompress(d):  # mirror of depack_lzss.py, for the self-test
    out_size = struct.unpack_from('<I', d, 0)[0]
    sp = 4
    ring = bytearray(N); r = 0xFEE
    out = bytearray(); flags = 0
    while len(out) < out_size and sp < len(d):
        flags >>= 1
        if not (flags & 0x100):
            flags = d[sp] | 0xFF00; sp += 1
        if flags & 1:
            c = d[sp]; sp += 1
            out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
        else:
            b0 = d[sp]; b1 = d[sp+1]; sp += 2
            offset = b0 | ((b1 & 0xF0) << 4); length = (b1 & 0x0F) + 3
            for i in range(length):
                c = ring[(offset + i) & 0xFFF]
                out.append(c); ring[r] = c; r = (r + 1) & 0xFFF
                if len(out) >= out_size: break
    return bytes(out)

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] != '--selftest':
        data = open(sys.argv[1], 'rb').read()
        comp = compress(data)
        open(sys.argv[2], 'wb').write(comp)
        ratio = len(comp) / max(1, len(data))
        print(f"{len(data)} -> {len(comp)} bytes ({ratio:.3f})")
        assert decompress(comp) == data, "round-trip FAILED"
        print("round-trip OK")
    elif len(sys.argv) == 3 and sys.argv[1] == '--selftest':
        data = open(sys.argv[2], 'rb').read()
        comp = compress(data)
        ok = decompress(comp) == data
        print(f"selftest {sys.argv[2]}: {len(data)} -> {len(comp)} ({len(comp)/max(1,len(data)):.3f})  round-trip {'OK' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)
    else:
        print(__doc__); sys.exit(1)
