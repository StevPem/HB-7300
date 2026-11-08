# Firmware update container (`.dat`) format

Fully reverse-engineered (orchestrator `FUN_20025AE4`, MD5-verify+flash `FUN_20024DB8`) and
**empirically verified** (sections 0 and 1 MD5-match with standard MD5). This is what the
repack/reseal toolchain targets.

## Layout
```
offset   size      field
0x00     4         magic  "3wfU"
0x04     12        version string  "3.112.003.16"
0x10     7 x u32   SECTION LENGTHS  (little-endian)                        } 0x2C header
0x2C     hdr[0]    section 0 DATA  = MAIN-CPU flash image (maps to flash 0x18000000)
         16        MD5(section 0 data)
         hdr[1]    section 1 DATA   + 16-byte MD5
         hdr[2]..  further sections (DSP Program / DSP Data / FPGA …) + MD5 each
...      2         end marker  "7e"  (0x37 0x65)
```
- **Each of the 7 header u32 is a section length.** Sections are concatenated, **each followed
  by a 16-byte `MD5()` of its own data**. Verified: `MD5(file[0x2C : 0x2C+hdr[0]]) ==`
  the 16 bytes at `0x2C+hdr[0]` (section 0, the 2.4 MB MAIN image), and likewise section 1.
- **Partial updates:** a `.dat` only carries the sections being updated, so the present sections
  don't sum to the (full-device) header. The example file has section 0 (MAIN, `0x252BF0`) and
  section 1 present; the rest is the DSP/FPGA payload.
- **Sections 2+ (DSP/FPGA)** use an inner **address/length record** sub-format (not the simple
  data+MD5 of the MAIN image) — not yet fully modelled; not needed to mod the MAIN CPU.

## Integrity & flashing (from the code)
- Integrity is **standard MD5 per section** — **no signature** (see `modding-feasibility.md`).
  `FUN_20024DB8` streams each section in 64 KB chunks, runs MD5 update, and **compares each
  64 KB block against current flash — only erasing+programming blocks that differ** (differential
  update, minimises wear/time). An MD5 mismatch aborts with the error path.
- File is validated first by magic `3wfU` + model-ID fields + the `7e` end marker
  (`FUN_200253F4`/`FUN_200247E4`).

## Re-sealing a modified MAIN image
Because integrity is a keyless MD5, a modified section can be re-sealed by recomputing its MD5:

```
depack_lzss.py  → modify → (re-LZSS-compress) → place back in section 0 (keep length hdr[0]
                 if it fits) → reseal.py reseal firmware.dat out.dat   # fixes section 0's MD5
```

`tools/reseal.py` verifies all simple sections and re-computes their MD5 trailers. Proven:
round-trip on an unmodified file is **byte-identical**, a MAIN-image edit re-seals to a valid
MD5, and the DSP/FPGA region is left untouched. If a modification changes section 0's **length**,
update `hdr[0]` too (subsequent sections shift).

## Status
- ✅ Header, section-length semantics, per-section MD5 integrity, differential 64 KB flash — all verified.
- ✅ Working reseal for the MAIN image (`tools/reseal.py`).
- ✅ Firmware-compatible LZSS **compressor** (`tools/pack_lzss.py`, round-trip verified) and full
  **repack chain** (`tools/repack_main.py`): extract → modify → recompress → re-seal, demonstrated
  end-to-end (produces a valid .dat whose MAIN image decodes to the modified bytes).
- ◻ DSP/FPGA section inner record format — open (only needed for DSP/FPGA mods).
