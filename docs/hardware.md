# IC-7300 hardware map & feature-feasibility matrix

Silicon identified from the official IC-7300 schematic (cross-checked against the firmware).
This is the "what belongs where" reference for adding features.

## Core silicon (BOM)

| Part | Role | Memory / size | Notes |
|------|------|---------------|-------|
| **Renesas R7S721000** (RZ/A1, Cortex-A9) | MAIN CPU — UI, control, menus, CI-V, file I/O | **~10 MB on-chip SRAM**, no external DRAM | 48 MHz xtal → PLL ≈400 MHz; runs the firmware we reverse-engineered |
| **TI TMS320C6745** (C674x float DSP) | IF-DSP — demod, filters, NR/NB/notch, AGC, scope FFT, the modes | **256 KB on-chip L2** + 32 KB L1; **no external DRAM** | ~375–456 MHz, single-precision float; booted by the MAIN CPU ("DSP Program:"/"DSP Data:") |
| **Altera Cyclone IV EP4CE55** (`EP4CE55F23I7N`) | FPGA — direct-sampling ADC capture + DDC/DUC | 55 K logic elements | Altera bitstream; the "FPGA" half of "DSP/FPGA firmware" |
| TI **PCM1802** / **PCM1754** | audio ADC / DAC (TX/RX audio codec) | — | |
| Microchip **23LC1024** | SPI SRAM scratch/buffer | 128 KB (serial) | not usable as DSP main memory |
| Winbond **W25**-series | SPI NOR flash — firmware storage | — | holds MAIN + DSP + FPGA images (`3wfU` container) |

**Memory headline:** neither programmable core has large RAM. MAIN CPU ≈10 MB on-chip
SRAM (mostly used by the running firmware); DSP **256 KB**, no DRAM on either. There is no
multi-MB working memory anywhere on the board.

## Processing pipeline

```
antenna ─► ADC ─► Cyclone IV FPGA (DDC: down-convert/decimate) ─► TMS320C6745 DSP
                                                                   (demod, filters, NR/NB/
                                                                    notch, AGC, scope FFT,
                                                                    FM/AM/SSB/CW/RTTY)
                                                                        │ audio
                                   PCM1754 DAC ◄── DSP ◄───────────────┘
   RZ/A1 MAIN CPU  ── commands/boots ──► DSP & FPGA ;  drives LCD/touch/CI-V/SD
```
IQ/baseband lives in the FPGA→DSP path. The MAIN CPU never sees raw IQ — only control +
processed audio/metering. Any modem (FreeDV/FT8) needs that IQ/audio, i.e. the DSP/FPGA side.

## Feature-feasibility matrix

| Feature | MAIN CPU (RZ/A1) | DSP (C6745, 256 KB) | FPGA (Cyclone IV) | PC (USB) | Companion SBC |
|---------|------------------|---------------------|-------------------|----------|----------------|
| **RADE / FreeDV V2** (neural, ~12–16 MB float32 weights) | ❌ weights > total RAM; no IQ | ❌ **~48× too little RAM**; DSP saturated | ❌ would need an HDL NN accelerator | ✅ freedv-gui today | ✅ Pi 4/5 runs `rade_c` |
| **FT8** (FFT + LDPC, needs accurate time base) | ❌ heavy; no IQ/audio path | ⚠️ maybe fits compute, but 256 KB + saturated + no toolchain access | — | ✅ WSJT-X today | ✅ |
| **Classic FreeDV** (Codec2 700D/E, light DSP) | ❌ no IQ/audio path | ⚠️ plausibly fits, but needs DSP f/w + 256 KB budget + audio taps | — | ✅ | ✅ |
| **CW decoder** (narrowband envelope/Goertzel, light) | ❌ **no audio tap** — codecs are on the DSP (see rx-signal-access.md) | ✅ natural fit (audio is here); tiny — but gated on DSP blobs+toolchain | — | ✅ | ✅ |
| **UI / menu / CI-V tweaks** | ✅ reachable & flashable (no signature) | — | — | n/a | n/a |

Legend: ✅ feasible · ⚠️ conceivable but gated · ❌ infeasible.

## Why the DSP route is closed for RADE but open for light work
- **Closed for ML:** RADE v1 weights (~12 MB) vs the C6745's **256 KB** on-chip RAM and no
  external DRAM — a ~48× memory shortfall, before compute. No amount of firmware skill adds RAM.
- **Open for light DSP:** the C6745 is a **standard TI part** — public ISA, Code Composer
  Studio / C6000 toolchain, Ghidra/IDA support, documented host-boot. So its firmware blobs
  (the "DSP Program"/"DSP Data" images in flash, beyond the MAIN update file) are reversible
  and, in principle, modifiable for features that fit 256 KB and spare cycles.

## Practical guidance
- **FreeDV/RADE, FT8:** use a **PC (freedv-gui / WSJT-X)** over the USB audio+CAT link, or an
  **external SBC companion** (the "HB-7300" homebrew box). These are where multi-MB float ML
  belongs; both work with an unmodified radio.
- **On-radio custom firmware** (the no-signature "GO" from `modding-feasibility.md`): aim at
  light MAIN-CPU features (UI/menu/CI-V) and, eventually, a **CW decoder** — not ML modems.
- **To ever touch the DSP/FPGA:** first obtain their firmware blobs (flash regions
  `0x18400000`/`0x187F0000`, versions `SX3765 V0.30`/`V0.9H`) and the main↔DSP load/command
  protocol; then assess within the 256 KB ceiling. Larger, separate project.
