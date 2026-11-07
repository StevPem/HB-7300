# HB-7300 — Icom IC-7300 firmware reverse engineering

Reverse-engineering notes, tooling, and a reconstructed CI-V command reference for the
**Icom IC-7300** HF/50 MHz transceiver firmware.

> **No copyrighted material is distributed here.** This repo contains only original
> analysis, documentation, and tools. The Icom firmware binary and the embedded
> proprietary fonts (Iwata Corp.) are **not** included — you supply your own firmware
> `.dat` (e.g. from Icom's official update) to reproduce any result. See
> [Legal / scope](#legal--scope).

---

## What the IC-7300 runs

| Property | Finding |
|----------|---------|
| SoC | **Renesas RZ/A1** (ARM **Cortex-A9**, ARMv7-A) |
| Code storage | serial/NOR **flash @ `0x18000000`** (64 MB mapped) |
| RAM | ~10 MB on-chip SRAM **@ `0x20000000`** |
| Peripherals | RZ/A1 block **@ `0xFCF00000`** (device memory) |
| RTOS | Renesas µITRON-style kernel (`GRP_FS` filesystem layer) |
| Middleware | FAT12/16/32 SD driver, **libpng 1.6.12**, **FreeType2**, **OpenVG** |
| UI graphics | **OpenVG vector** pipeline + TrueType fonts + a few 8-bpp bitmaps |
| Control | **CI-V** (CAT) over serial + USB CDC |
| Analyzed version | firmware **v1.42** — internal tag `SX3765 V4.96-000` |

## Firmware layout (`.dat` update file)

```
0x000000  44-byte vendor header:  "3wfU" magic + "3.112.003.16" + 7x u32 region table
0x00002C  ARM image, maps to flash 0x18000000:
            - plaintext ARM boot stub (reset vector table, MMU/cache bring-up)
            - LZSS-compressed main application  (-> 3.52 MB @ RAM 0x20005000)
~0x170000  0xFF erased-flash padding
0x210000+  resource section: 2 Iwata TrueType fonts + OpenVG vector art + 8-bpp bitmaps
```

### Boot chain (fully traced)
1. **Flash stub @ `0x18000000`**: sets clocks (`0xFCFE00xx`), disables MMU/caches, sets
   `VBAR`, copies a 0x650-byte loader to RAM `0x20004000`, jumps to it.
2. **RAM loader @ `0x20004000`**: Cortex-A9 cache set/way maintenance, builds an MMU
   section table (flash / SDRAM / peripherals), then LZSS-decompresses the main app to
   `0x20005000` and jumps in.
3. **Decompressor** = Okumura **LZSS** — 4096-byte ring buffer, init index `0xFEE`,
   12-bit offset / 3–18-byte matches. Reimplemented in [`tools/depack_lzss.py`](tools/depack_lzss.py).

### Graphics (the non-obvious part)
The large high-entropy flash blobs are **not compressed bitmaps** — they are **OpenVG
vector data** (paths, coordinates, paint colors) consumed by a display-list builder
(`FUN_20160110`). Confirmed by the OpenVG API strings (`vgCreatePath`, `vgCreatePaint`,
`vgCreateFont`, `vgCreateImage`, `TxtRender_VG_*`). Only small assets (dial, letterforms)
are raw 8-bpp — see [`tools/render_assets.py`](tools/render_assets.py). Full history of the
(failed) raster/compression attempts and how emulation resolved it is in the report.

## CI-V / CAT command set (reconstructed from firmware)

The live CI-V engine was reversed, not copied from Icom docs:

- per-port **frame assembler** (`FE FE … FD` byte state machine) → **router**
  `FUN_2000b258` → **interpreter** `FUN_2000b03c`;
- interpreter is **table-driven**: command byte (`<0x2B`) indexes a command table
  `@0x2018AA2C` (8 B/entry) → subcommand list → capability table `@0x2018AB84`
  (16 B/entry: permission flags + min/max payload length) → **143-case handler**
  (`FUN_201114C8`).

The complete table (33 commands, **143 command/subcommand combinations**, with payload
lengths) is in [`docs/CI-V_command_table.md`](docs/CI-V_command_table.md) and can be
re-dumped with [`tools/civ_extract.py`](tools/civ_extract.py). It self-validates against
known CI-V (set-freq = 5 BCD bytes; read commands = length 0 + read-only flag) and reveals
version detail: the dual-watch `0x25/0x26` commands are present, while `0x0C/0x0D/0x12/0x1F`
are present-but-disabled (matching IC-7300 hardware: no freq-offset, single antenna, no DV).

## Reproduce

```bash
# 0. obtain your own IC-7300 firmware .dat (Icom official update) -> ic7300_firmware.dat

# 1. decompress the main application (LZSS)
python3 tools/depack_lzss.py ic7300_firmware.dat 0x1002c main_image.bin
#    -> valid bytes are the first 3,524,204; load as raw ARM:LE:32:v7 at base 0x20005000

# 2. dump the CI-V command table
python3 tools/civ_extract.py main_image.bin        # (truncate padding is optional)

# 3. render the raw 8-bpp UI bitmaps (needs Pillow)
python3 tools/render_assets.py ic7300_firmware.dat

# 4. load into Ghidra with flash mapped, for interactive RE (needs PyGhidra + Ghidra 12.1.x)
GHIDRA_INSTALL_DIR=/path/to/ghidra python3 tools/ghidra_load.py main_image.bin ic7300_firmware.dat
```

## Repo contents

```
docs/IC-7300_firmware_analysis.md   full analysis report (container, boot, LZSS, OpenVG, CI-V, roadmap)
docs/CI-V_command_table.md          reconstructed CI-V command/subcommand reference
docs/menu_labels.md                 full menu label map (262 items; the menu-resolver output)
tools/depack_lzss.py                LZSS depacker (main image extractor)
tools/civ_extract.py                dump the CI-V command table from the image
tools/render_assets.py              render the raw 8-bpp UI bitmaps
tools/ghidra_load.py                PyGhidra loader (correct base + flash mapped)
```

## Roadmap — what's left to fully understand the firmware

`[here]` = reachable from the main-CPU image alone · `[needs artifacts]` = needs a full
flash dump, the DSP/FPGA images, or hardware.

| # | Layer | Scope | Status |
|---|-------|-------|--------|
| 1 | Boot→runtime | `0x200045D0`→`main`→RTOS init→task graph→event loop; identify µITRON variant | `[here]` |
| 2 | Hardware/peripherals | `0xFCFExxxx` map + drivers: VDC5 LCD, touch, I²S codec, UART, USB, SPI/SD, GPIO | `[here]` |
| 3 | **DSP/FPGA signal path** | direct-sampling ADC/DDC + DSP demod/filter/AGC/NR math | **`[needs artifacts]`** |
| 4 | **CI-V / CAT** | command table, params, effects | **done** (this repo) |
| 5 | Radio control | band/PLL, BPF+relays, internal ATU, SWR/power metering, TX gain/ALC, scope flow | `[here]` |
| 6 | Settings/cal/service | menu model, calibration data layout, ADJUST-mode entry/functions | `[here]` |
| 7 | Graphics pipeline | interpret OpenVG path format / emulate renderer; map screen resource manager | `[here]` |
| 8 | Update & integrity | 7-entry header-table semantics, checksum/signature, full multi-image flash layout | `[here]` |
| 9 | Audio | voice memory record/playback (WAV), voice synth, RTTY/PSK decoders | `[here]` |
| 10 | Dynamic analysis | QEMU RZ/A1 / full-system emulation to *run* the firmware | optional |

**Bottom line:** most remaining layers are reachable from the main-CPU image with the
tooling here. The irreducible gap is **layer 3** — the actual DSP/FPGA signal processing —
which needs a full flash dump or Icom's DSP/FPGA update images; this file only exposes the
*control* side of that interface.

## Legal / scope

For interoperability, education, and security research on hardware you own. Analysis uses
a firmware image **you supply**. This repository distributes no Icom firmware (copyright
Icom Inc.) and no embedded fonts (proprietary, Iwata Corp.) — the `.gitignore` keeps those
and all firmware-derived binaries out. Rendered UI artwork is derived from Icom's
copyrighted assets; do not redistribute it. Respect your local laws on reverse engineering
and Icom's licensing.
