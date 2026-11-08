# Icom IC-7300 Firmware — Reverse Engineering Report

**Target file:** `5b494b67-7300_142.dat` (uploaded; filename implies IC‑7300 update **v1.42**)
**Size:** 3,954,089 bytes (0x3C55A9)
**SHA‑256:** `8cf5324a126f105cd2307c30b191b9dd8183f86b2c8bf229e61bf9a6a8c32f32`
**Tooling:** REA 6.8.0 CLI (region/artifact routing), capstone 5.0 (ARM disassembly), custom LZSS depacker, Ghidra 12.1.3 (auto‑analysis).
**Scope:** This is legitimate study of firmware for a radio you operate. Analysis is static only — nothing was flashed, transmitted, or executed.

---

## 1. Executive summary

The `.dat` file is **not** an encrypted blob — it is a flat image for a **Renesas RZ/A1 (ARM Cortex‑A9)** system consisting of a small plaintext ARM boot stub followed by an **LZSS‑compressed main application**. By disassembling the boot stub I recovered the exact decompressor and used it to unpack the main firmware:

- **3,524,204 bytes (3.36 MB)** of valid IC‑7300 main‑CPU application, loaded at **`0x20005000`**.
- Confirmed via a clean ARM vector table, correct relocation of all literals to `0x2000xxxx`, entropy dropping from ~7.6 (compressed) to ~5.6 (code), and ~6,800 coherent strings.
- Embedded string **`SX3765 V4.96-000`** — **correction:** this is a *compatibility version check for the front-panel/display MCU* (IC501, Renesas RL78, marked `SX-3765C-1`), **not** the main firmware's own version (the user-facing version is v1.42). See Related work.

The decompressed image reveals the full software stack: the **FreeRTOS** kernel (Renesas RZ/A1H port, with Icom customizations), a FAT12/16/32 SD‑card driver, libpng + FreeType2 + OpenVG for the color display, the CI‑V (CAT) control protocol, and the DSP/FPGA supervision for the direct‑sampling SDR receiver. Ghidra auto‑analysis of the clean image recovered **6,743 functions** and detected **embedded PNG image assets** (UI graphics) at `0x200CE460`, `0x200E6DD4`, …

---

## 2. Container / header format

The first **0x2C (44) bytes** are a vendor header; the ARM image begins at file offset `0x2C`.

| Offset | Size | Field | Value |
|-------:|-----:|-------|-------|
| 0x00 | 4 | Magic | `33 77 66 55` = ASCII `3wfU` |
| 0x04 | 12 | Version string | `3.112.003.16` |
| 0x10 | 4×7 | u32 LE table | see below |
| 0x2C | … | ARM image (maps to `0x18000000`) | — |

The 7‑entry u32 table at `0x10`:
`0x00252BF0, 0x00017E46, 0x00027F08, 0x000B03AC, 0x000AFF08, 0x000AA759, 0x000D1D14`.
All seven have a `0x00` high byte (values < ~14 MB). They are region descriptors (per‑image sizes/offsets or checksums) for the device's **full multi‑image flash**, most of which is not present in this single update file (see §7). Their exact semantics are not fully determined from this partial image — stated as a limitation, not a conclusion.

---

## 3. SoC & memory map

Identified from the stage‑2 loader's MMU page‑table builder and confirmed by strings (`RENESAS RZ/A1 SD Driver Ver4.01`).

**CPU:** ARM Cortex‑A9 (ARMv7‑A) — uses `movw`, `VBAR` (`mcr p15, c12`), CCSIDR set/way cache ops, `isb/dsb sy`.

| Region | Purpose | Evidence |
|--------|---------|----------|
| `0x18000000` (64 MB mapped) | NOR/serial **flash** (firmware storage, XIP for the stub) | VBAR + reset handlers at `0x1800xxxx`; page‑table maps 64 sections |
| `0x20000000` (~10 MB) | **SDRAM / on‑chip RAM** (RZ/A1 has 10 MB internal SRAM) | stack `0x2080D000`; main image relocated here |
| `0x3FE00000` (1 MB) | internal SRAM / boot area | page‑table entry, attr `0xC12` |
| `0xFCF00000`–`0xFCFFFFFF` | **on‑chip peripherals** (device memory) | page‑table maps 0x31 sections attr `0xC12`; stub writes to `0xFCFE0010/14/0408` |

---

## 4. Boot chain (fully disassembled)

### Stage 1 — flash boot stub (runs in place at `0x18000000`)

ARM exception vector table at `0x18000000` (file `0x2C`). Reset handler `0x1800008C`:

```
reset:
    ldr  r0,=0x3FFFFF80 ; str #1          ; release/kick a control reg
    ldr  r0,=0xFCFE0010 ; strh #0x1035     ; peripheral (clock/standby) init
    ldr  r0,=0xFCFE0014 ; strh #1
    ldr  r0,=0xFCFE0408 ; strb #0xF
    mrc/bic/mcr p15,c1,c0                   ; SCTLR: disable MMU, I/D cache, branch pred, alignment
    bl   set_VBAR                           ; mcr p15,c12,c0 -> VBAR = 0x18000000
    ldr  sp,=0x2080D000                     ; stack in SDRAM
    bl   copy_init                          ; copy 0x650 bytes flash 0x18004000 -> RAM 0x20004000
    bl   jump_via_ptr                       ; ldr pc,[=0x200045D0]  -> enter stage 2 in RAM
```

`copy_init` is a simple word loop copying **0x650 bytes** from flash `0x18004000` → RAM `0x20004000`; control then jumps to `0x200045D0` inside that copied code.

### Stage 2 — RAM loader (`0x20004000`, entry `0x200045D0`)

Disassembled in full (0x650 bytes). Contents:

- **`0x20004000` cache maintenance:** reads `CCSIDR`/`CLIDR` (`mrc p15,1,…`), iterates cache levels/sets/ways issuing `DCISW/DCCSW/DCCISW` (`mcr p15,0,…,c7,c6/c10/c14`) — textbook Cortex‑A9 cache clean/invalidate.
- **MMU/MPU helpers:** set `TTBR0` (c2), `DACR` (c3), `SCTLR` (c1); enable I‑cache + branch prediction (bits `0x1004`); TLB invalidate (`c8,c7`); I‑cache invalidate (`c7,c5`).
- **`0x200044B8` page‑table builder** → builds a 1 MB‑section table at `0x20000000` and maps flash/SDRAM/`0x3FE00000`/`0xFCF00000` as in §3, then enables the MMU.
- **`0x2000425C` LZSS decompressor** (see §5).
- **`0x20004374` image selector:** `memcmp(flash 0x187F0000, "SX3765 V1.00-003", 16)`. If match → unpack from `0x18400000`, else from `0x18010000`; destination **`0x20005000`**; the first 32‑bit word of the source is the uncompressed length.

In this update file both `0x18400000` and `0x187F0000` lie **past end‑of‑file**, so the present image is the one at `0x18010000` (file `0x1002C`).

---

## 5. The LZSS decompressor (recovered algorithm)

Classic Haruhiko Okumura LZSS, identified unambiguously by the ring‑buffer init position **`0xFEE` (4078 = N−F)**:

- Ring buffer **N = 4096 (0x1000)** bytes, initialized to `0x00`, write index starts at `0xFEE`.
- Control bytes: 1 flag byte, LSB‑first; **bit=1 → literal**, **bit=0 → back‑reference**.
- Back‑reference = 2 bytes `B0,B1`:
  - **offset** = `B0 | ((B1 & 0xF0) << 4)` (12‑bit, 0..4095)
  - **length** = `(B1 & 0x0F) + 3` (3..18 bytes), copied from the ring buffer at `(offset+i) & 0xFFF`.
- Output terminates at the declared uncompressed length.

This matched perfectly: output began with the expected `E59FF018` vector table and produced coherent code/strings with no mid‑image gaps. A 50‑line Python reimplementation (`depack_lzss.py`) reproduces it.

---

## 6. Decompressed main application

- **Load address:** `0x20005000`. **Valid size:** 3,524,204 bytes (`main_image_clean.bin`); the declared length (`0x390B18`) includes a trailing `0xFF` pad region.
- **Vector table** at `0x20005000`; reset `0x20005050`, handlers `0x200050CC`, `0x200056DC`, …
- **`SX3765 Vx.xx` strings** are front-panel-MCU (RL78) compatibility checks, not the main app version (see correction above); the history table lists the display-MCU versions `V3.41…V4.96`.

### Subsystem / feature map (string‑ and structure‑backed)

| Subsystem | Evidence |
|-----------|----------|
| **RTOS** | **FreeRTOS** (Renesas RZ/A1H port AN R01AN5093, Icom-customized) — corrected from an earlier "µITRON-style" guess; `GRP_FS` filesystem layer sits on top |
| **SD card + FAT** | `RENESAS RZ/A1 SD Driver Ver4.01`; `FAT12/16/32`, cluster/EOC management; paths `C:\IC-7300\{Voice,VoiceTx,Decode\Rtty,Capture,Setting,IC-7300_factory}` |
| **Voice memory / recording** | `voicetx1..8.wav`, "Memory TX and Data Saving to SD supported" |
| **Display / GUI** | **libpng 1.6.12**, **FreeType2** (`TxtRender_FT2_*`, TrueType glyph paths), **OpenVG** (`TxtRender_VG_*`) for the 4.3" color touch TFT |
| **Touch & service** | `Touch Screen Calibration`, `TW Calibration`, `ADJUST MODE`, `SX-3765 Adjust`, `REF Adjust` (TCXO reference cal) |
| **CAT control** | **CI‑V**: `CI-V Address/Baud Rate/Transceive/USB`, `CI-V Output (for ANT)` |
| **Spectrum scope (SDR)** | `FFT Scope`, `Waterfall Display`, `SPAN`, `REF Level`, `Center/Carrier Point Center`, `M.SCOPE`, `AUDIO SCOPE` |
| **DSP / FPGA** | `DSP/FPGA firmware is wrong`, `DSP Program:`, `DSP Data:`, `DSP TX TotalGain HF/50M/70M`, preset DSP TXG — main CPU supervises the direct‑sampling DSP/FPGA chain |
| **Modes / radio** | `CW-R`, `SPLIT`, PBT (passband tuning) inner/outer dial, NOTCH, AGC‑F/M/S, RTTY (`45bps BAUDOT Mark=2125Hz Shift=170Hz`), Preset/Memo‑pad memory |

This matches the IC‑7300's known architecture: a **direct‑sampling SDR** (ADC/FPGA front end + DSP) controlled by an RZ/A1 applications processor driving the color touchscreen UI and CI‑V remote control.

---

## 7. Full flash layout (as seen in this file)

| File offset | Content |
|------------:|---------|
| `0x000000`–`0x00002B` | 44‑byte vendor header |
| `0x00002C`–`~0x16E000` | **Main app**, LZSS‑compressed (→ 3.36 MB @ `0x20005000`) |
| `~0x170000`–`0x210000` | `0xFF` erased‑flash padding (~640 KB) |
| `0x210000`–`0x24FFFF` | lower‑entropy data/tables (fonts, factory data?) |
| `0x250000`–`0x3C55A9` | further high‑entropy (another compressed blob — likely DSP/FPGA or voice/font image) |

The stage‑2 selector references additional images at `0x18400000` and `0x187F0000` that are **beyond this file**, so the device's complete flash is larger and multi‑image; this update delivers the subset above.

---

## 7a. The "second blob" unpacked — it's a resource section, not one image

Follow‑up investigation of the tail (`0x210000`→EOF) shows it is **not** a single compressed/encrypted blob. It is the firmware's **resource section**, confirmed by `0x182xxxxx` pointer constants inside the decompressed main app:

**Embedded fonts (extracted as valid TrueType, verified with `file`):**

| Flash addr | File off | Size | Font `name` | Notes |
|-----------|---------|-----:|-------------|-------|
| `0x18210000` | `0x210030` | 176,700 B | **`ICOMp_UD_Medium_JP`** | Iwata Corp., v001.02 2015/11/6, 18 tables, CJK (vhea/vmtx) → `ui_font.ttf` |
| `0x18240000` | `0x240030` | 25,634 B | **`SUDGoDspIWA-HW-Md`** | Iwata SUD Gothic Display, half‑width → `ui_font2.ttf` |

(Both carry `Copyright (C) 2015 Iwata Corporation` — proprietary licensed typefaces; extracted here only for analysis of your own device.)

**Graphics/asset bank:** flash `0x18250000`→EOF (~1.5 MB). Proven characteristics:
- **Not encrypted:** byte histogram is strongly non‑uniform (χ² ≈ 3.18M vs ~293 for random; dominant bytes `0xFF/0x00/0x11/0x22/0x21/0x10` — a nibble‑packed pattern typical of ≤8‑bpp bitmaps).
- **Not a single framed stream:** no valid zlib/gzip/lzma/LZSS‑code framing; the hundreds of "zlib" byte hits are random false positives.
- **Individually addressed assets:** ~12 distinct `0x1825xxxx–0x183xxxxx` pointers from the app, plus a 24‑byte descriptor table at `main+0x323D44` whose records are `{flash_ptr, flags, bpp=0x08, width, height, …}` — e.g. `{0x18250000, …, 8bpp, 0x9A×0x2C}`, `{0x182504A4, …, 8bpp, 0x96×0x15}`. These are **display bitmaps/icons**; some palettized (repeating `6A 6B` pixel runs), some high‑entropy (per‑asset compressed or photographic, e.g. the startup screen).

**Conclusion:** the tail decodes to **two Iwata UI fonts + an 8‑bpp graphics/asset bank**, accessed by absolute flash pointer at runtime — there is no monolithic second image to decompress.

### 7b. Bitmap format cracked — real icons rendered

The uncompressed assets are **8‑bits‑per‑pixel grayscale bitmaps** (intensity/alpha masks the UI blits in a chosen color). Each asset's byte length = `next_pointer − this_pointer`; width was recovered by row‑to‑row autocorrelation and cross‑checked against the descriptor fields.

| Flash addr | Size | Dimensions | Content |
|-----------|-----:|-----------|---------|
| `0x18250000` | 1,188 B | **36 × 33**, 8bpp | circular dial/ring icon (36×33 = 1188 exactly) |
| `0x182504a4` | 6,864 B | **156 × 44**, 8bpp | letterform/logo glyphs — matches descriptor `width≈154, height=44` |

Row‑autocorrelation scores of 0.76 / 0.83 confirm clean raster structure, and the rendered PNGs show coherent, anti‑aliased graphics — proving the format. Rendering code: load `width×height` bytes as PIL mode `'L'`.

**Compressed assets (codec investigation):** the large resources (`0x182850f0` 258 KB, `0x182c42ff` 156 KB, `0x182ea552` 100 KB, `0x18341234`/`0x18380184` ~280 KB, …) are **proprietary‑compressed** — the UI backgrounds, band‑scope art and startup screen. I ran a full elimination against them:

| Test | Result |
|------|--------|
| Raw 8‑bpp / 4‑bpp raster, widths 8–300 | ✗ row‑autocorrelation ≤ 0.12 at every width |
| Raw 16‑bpp RGB565, widths 120–578 | ✗ inter‑row channel diff ≈ 32/31 (uncorrelated) at every width |
| Firmware's own LZSS (N=4096) | ✗ output stays entropy ≈ 7.1 |
| zlib / raw DEFLATE (libpng is present), wbits ±9…47, 6 start offsets | ✗ no valid stream |
| Encryption | ✗ byte histogram non‑uniform (χ² ≫ uniform); redundancy present |
| Per‑column (period 9/18) flag analysis | ✗ no low‑entropy control column |

Established facts: entropy ≈ 6.9–7.1 (compressed, not encrypted, not raw); a recurring **~18/36‑byte marker period** (high‑byte `0xFF` ≈ 10%, visible as drifting diagonal stripes when rendered at any width); and at least one asset (`0x182c42ff`) is **palette‑indexed** — an RGBA palette (`0xFFFFFFFF` white, `0x808080FF` gray, …) is stored inline right after its pointer. So the format is an indexed‑color image under a custom entropy/marker codec.

### 7c. Decoder hunt (Thumb‑2) — why it is gated behind a resource manager

A working Ghidra decompiler pipeline was built (PyGhidra, image at `0x20005000` **plus** flash mapped at `0x18000000`, 6,759 functions, full C pseudocode). The decoder was still not isolated, for a concrete and documented structural reason:

- The compressed‑asset pointers (`0x182ea552`, `0x182c42ff`, …) each occur **exactly once** in the image, inside **scattered descriptor structs** — not in any code literal pool.
- Those descriptor addresses have **0 code xrefs**; an exhaustive scan of all 389,725 instructions found **no instruction** with a scalar operand in the resource range.
- Conclusion: the UI reaches resources through a **resource manager that computes `&table[id]`** at runtime (resource‑ID dispatch), so there is no static code→resource edge to follow to the blitter/decoder.

Reaching the decoder therefore needs either (a) tracing the resource‑ID indexing from a known screen‑draw entry point through the manager, or (b) dynamic analysis — emulating the decode routine (e.g. Unicorn) with a known asset + its palette and capturing the output framebuffer. Both are feasible but are a separate, larger effort; this report stops at the honest boundary rather than presenting a guessed decode.

### 7d. Resolution via emulation — the graphics are OpenVG vector data, not compressed bitmaps

A Unicorn (ARM/Thumb‑2) harness was built: flash mapped at `0x18000000`, full RAM at `0x20000000`, the 1,247 loop+byte‑copy candidate functions each executed against an asset. The emulation led to `FUN_20160110`, which turned out **not** to be a bitmap decompressor but a **vector‑graphics display‑list builder** — it emits hardware graphics command words (`0x14008000`, `0x19002078`, `0x190020FC`, …), packs width/height from a dimensions struct, and dispatches through a paint/function‑pointer table.

That pointed to the real architecture, which the strings confirm outright — the UI is **Khronos OpenVG**:

`OpenVG` · `vgCreatePath` · `vgCreatePaint` · `vgCreateFont` · `vgCreateImage` · `DesignVector` · `TxtRender_VG_Create/Glyph/GlyphImg/Destroy`

So the IC‑7300 renders its UI with a **vector pipeline**: OpenVG paths + the two Iwata TrueType fonts (rasterized per‑glyph via `vgCreatePath`/`vgCreateFont`) + the small 8‑bpp bitmaps (used as OpenVG images/masks — the dial and letterforms already rendered). **This is why the large high‑entropy flash blobs never decoded as rasters at any width/depth, codec or palette: they are OpenVG vector resource data (path segments, coordinates, paint colors — consistent with the ~18‑byte segment period and inline RGBA), not compressed pictures.** There is no single "startup‑screen bitmap" to decompress; screens are composed at runtime from vectors, fonts and masks by the OpenVG renderer.

**Net graphics result:** the uncompressed 8‑bpp image assets are decoded and rendered (dial, letterforms); the "compressed blobs" are identified as **OpenVG vector/path resource data** (confirmed by the OpenVG API and the decompiled display‑list builder), not a raster codec — which is the correct resolution of why raster/compression decoding was impossible. Rendering a full vector scene would require interpreting the OpenVG path format or emulating the renderer end‑to‑end (a further, larger effort).

## 8. Limitations & honest unknowns

- The 7‑entry header table's exact field meaning is **not proven** (sizes vs offsets vs CRCs).
- The trailing 214 KB of the declared uncompressed length is `0xFF` padding; the ~3.36 MB before it is the solid, verified image.
- Secondary blobs at `0x210000+` and the referenced `0x18400000`/`0x187F0000` images are **not unpacked** here (DSP/FPGA/voice/font candidates).
- Function‑level semantics beyond the boot chain were not hand‑traced; Ghidra auto‑analysis of the clean image (**6,743 functions**, base `0x20005000`, ARM:LE:32:v7) is available in `ghidra_proj2` for deeper work (decompiler, xrefs). Function inventory exported to `funcs.json`.

## 9. Reproduce

```bash
# 1. header + base address are self-evident (ARM vectors at file 0x2C, literals -> 0x18000000)
# 2. depack the main image:
python3 depack_lzss.py 5b494b67-7300_142.dat 0x1002c main_image.bin   # LZSS, N=4096, F=18, init 0xFEE
# 3. load main_image.bin as raw ARM:LE:32:v7, base 0x20005000, in Ghidra/REA
```

Artifacts in `/home/user/rea-work/`: `main_image.bin` (full), `main_image_clean.bin` (3.36 MB verified), `depack_lzss.py`, Ghidra projects `ghidra_proj`/`ghidra_proj2`.

---

## 10. Remaining work / roadmap to complete understanding

Legend: **[here]** = doable from this file; **[needs artifacts]** = requires a full flash dump, the DSP/FPGA images, or hardware.

| # | Layer | Scope | Status | Method | Effort |
|---|-------|-------|--------|--------|--------|
| 1 | Boot→runtime | Trace `0x200045D0`→`main`→RTOS init→task graph→event loop; identify FreeRTOS task set & syscalls | [here] | Ghidra decompiler from reset vector | S–M |
| 2 | Hardware/peripherals | Map `0xFCFExxxx` (clock/standby, INTC) + drivers: VDC5 LCD/framebuffer, touch, I²S codec, UART, USB, SPI/SD, GPIO (relays/PTT/fan) | [here] | RZ/A1 HW manual + MMIO xrefs | M |
| 3 | **DSP/FPGA signal path** | The direct-sampling core: FPGA ADC/DDC + DSP demod/filter/AGC/NR math | **[needs artifacts]** | Needs full flash or Icom DSP/FPGA images + separate toolchain; from *here* only the main-CPU side (load + control/register protocol) | L |
| 4 | **CI-V / CAT** | Full command dispatcher: command table, params, effects | [here] | Decompile dispatcher (in progress) | M |
| 5 | Radio control | Band/PLL, BPF+relays, internal ATU algorithm, SWR/power metering, TX gain/ALC, scope data flow | [here] | Ghidra + Unicorn | M–L |
| 6 | Settings/cal/service | Menu model, calibration data layout (TCXO/S-meter/SWR/power), ADJUST-mode entry & functions | [here] | Ghidra + flash-region analysis | M |
| 7 | Graphics pipeline | Interpret OpenVG path format / emulate renderer; map screen-definition resource manager (`&table[id]` dispatch) | [here] | OpenVG spec + Unicorn renderer emulation | L |
| 8 | Update & integrity | 7-entry header-table semantics, checksum/signature path, full multi-image flash layout | [here] | Static + cross-version diff | S–M |
| 9 | Audio | Voice memory record/playback (WAV), voice synth, RTTY/PSK decoders | [here] | Ghidra | M |
| 10 | Dynamic analysis | QEMU RZ/A1 / full-system emulation to *run* the firmware | [optional] | QEMU machine model or extended Unicorn | L |

**Bottom line:** ~70% (layers 1,2,4,5,6,7,8,9) is reachable from this file alone — a large but tractable static effort, now unblocked by the working decompiler + Unicorn pipeline. The irreducible gap is **layer 3** (the actual DSP/FPGA signal processing), which needs a full flash dump or Icom's DSP/FPGA update images; this main-CPU file only exposes the *control* side of that interface.

---

## 11. CI-V / CAT command set (reversed from firmware)

The live CI-V engine was located and reversed (not taken from Icom docs):

- **Per-port frame assemblers** (`FUN_2001099c` + siblings): byte state machine, `0xFE 0xFE` start → buffer (≤100 B) → `0xFD` end; fast-path transceive flags for cmd `0x00`/`0x01`/`0x1C·00`(PTT)/`0x1C·03`(tuner).
- **Frame router** `FUN_2000b258` → **command interpreter** `FUN_2000b03c`.
- Interpreter is **table-driven**: command byte (must be <`0x2B`) indexes a **command table @`0x2018AA2C`** (8 B/entry → type + subcommand-list pointer); the subcommand byte is matched in a `0xFD`-terminated list; a **capability table @`0x2018AB84`** (16 B/entry) gives permission flags + min/max payload length; execution goes through a **143-case handler dispatch** (`FUN_201114C8`).

The complete command/subcommand table (33 commands, 143 combinations, with payload-length limits) was dumped directly from these tables — see **`CI-V_command_table.md`**. Highlights: freq set/read `0x00/0x05/0x03` (5-byte BCD), mode `0x01/0x06`, levels `0x14` (18 subcmds), meters `0x15` (10), functions `0x16` (19), misc `0x1A` (20), scope `0x27` (16), and the dual-watch `0x25/0x26` commands that confirm this is late firmware. Commands `0x0C/0x0D/0x12/0x1F` are present-but-disabled (type 0), correctly matching IC-7300 hardware (no freq-offset, single antenna, no DV/GPS).

---

## 12. Menu string-resource resolver & label map

The on-screen menu labels are **direct inline ASCII pointers** inside static per-item
descriptors — not runtime-resolved resource IDs. Each item (≈48 bytes) is:

```
+0x00 item/screen id      +0x10 English label char*   +0x1C Japanese label char*
+0x04 type code           +0x14 shared marker 0x20359E5C   +0x24 value-list (char*[])
+0x08 1                   +0x18 0                         +0x28 handler (runtime RAM ptr)
+0x0C 0                   +0x20 marker 0x20359E5C         +0x2C flags (e.g. 0x00641301)
```

Scanning for the `+0x10 label` / `+0x14 == 0x20359E5C` pattern enumerates **262 menu
items**, 102 with explicit value-lists (e.g. `Filter`→FIL1/FIL2/FIL3, `Filter Type`→
SHARP/SOFT, `[NOTCH] Switch`→Auto/Manual/Auto-Manual, `Mode`→SSB/LSB/…/AM,
`SSB TBW`→WIDE/MID/NAR). Full list in [`CI-V_command_table.md`](CI-V_command_table.md)'s
companion [`menu_labels.md`](menu_labels.md).

This confirms the firmware is **bilingual** (English + Japanese labels per item) and
resolves the remaining CI-V `0x16` DSP settings as far as static analysis allows:
`0x56`=Filter Type (SHARP/SOFT), `0x57`=Filter (FIL1/2/3), `0x58`≈[NOTCH] Switch. The
per-item *handler* pointer is runtime-bound (BSS), so a few CI-V subcommands can't be tied
to a specific label statically — the item→handler map is built during boot, which would
need dynamic analysis (roadmap layer 10) to capture.

---

## 13. Dynamic analysis for the last four `0x16` subcommands (`4F/50/58/65/66`)

**Concrete state variables (resolved statically via the handlers' `DAT_` pointers):**

| Sub | Writes | Variable | Cluster |
|-----|--------|----------|---------|
| 65 | bit 3 of `*0x203902F9` (getter reads same) | `0x203902F9` | DSP control flags `0x203902D4–F9` |
| 66 | bit 5 (`0x20`) of `*0x203902D8` + triggers action | `0x203902D8` | DSP control flags |
| 58 | per-mode entry in table at `0x203DE4CC+0x26A` | `0x203DE4CC` | per-mode operating state `0x203DE1xx` |
| 50 | per-mode 2-value via callback (`0x203DE174`) | `0x203DE174` | per-mode operating state |
| 4F | (handler is a trampoline chain; variable not resolved) | — | — |

So `65/66` are **DSP global on/off flags** and `58/50` are **per-mode DSP settings** — the
precise memory each controls is known.

**Why the human label needs full-system dynamic analysis:** the menu-item → handler binding
is constructed in RAM at boot, and these handlers are reached through trampoline chains that
require live RTOS register/state context. A Unicorn harness that runs an isolated handler
**derails on an invalid instruction within ~18 hops** (verified), because the surrounding
state pointers aren't set up. Naming them therefore needs one of:

1. **Full-system emulation** — a QEMU **RZ/A1** machine model (not upstream) or a Unicorn
   harness with modeled RZ/A1 peripherals (clock/INTC/timers/VDC) + RTOS + the DSP/FPGA
   handshake. Large, and partly gated by the **layer-3 DSP/FPGA gap** (the DSP must answer
   during boot for menu init to complete).
2. **On-radio probing** (practical, for a radio owner) — read each subcommand over CI-V and
   watch which setting the radio reports, toggling to confirm. Tool:
   [`tools/civ_probe_radio.py`](../tools/civ_probe_radio.py). Read frames are non-destructive
   (`FE FE 94 E0 16 <sub> FD`); toggling asks first.

Static analysis is exhausted for these four; the setup and exact targets for both dynamic
routes are provided.
