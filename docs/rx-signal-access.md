# RX signal access on the main CPU — what a decoder can (and can't) see

Investigates what receive-side signal data the RZ/A1 main CPU can observe — the prerequisite
for any on-radio decoder (CW, digimodes). **Key result: the main CPU has no audio-rate tap.**

## Where the audio actually is (schematic-confirmed)
```
antenna ─► ADC ─► Cyclone IV FPGA (DDC) ─► TMS320C6745 DSP ─┬─► PCM1754 DAC ─► speaker/line
                                                            └─► PCM1802 ADC  (TX audio in)
   RZ/A1 MAIN CPU ◄── DSPCK/DSPR/FRM/BCLK/DSTB + HSK0/HSK1 ──► DSP   (control + status only)
```
Both audio codecs (**PCM1802 ADC**, **PCM1754 DAC**) sit in the **IF-DSP block wired to the
TMS320C6745** (MDAT/MCK/MSTB1/MSTB2/ECK/EDT). The **main CPU's only link to the DSP is the
`DSPCK/DSPR/FRM/BCLK/DSTB` host/control bus** — it carries commands, status, metering and scope
frames, **not** audio samples. The main CPU never touches the 12.288 MHz audio stream.

## What the main CPU *does* receive from the DSP
All of it is **processed and low-rate** (UI/poll cadence, ~tens of Hz), delivered over the host link:
- **Metering** — S-meter, SWR, ALC, PO, COMP, Vd, Id (the CI-V `0x15` sources). Passband-wide
  level, updated at display rate.
- **Scope frames** — spectrum/waterfall and audio-scope bins, a display refresh (~tens of Hz),
  RF-domain (or an audio-scope snapshot), not a continuous audio-rate stream.
- **Status/flags** — mode, filter, lock, etc.

Outbound is the 25-parameter DSP control surface documented in [`dsp-interface.md`](dsp-interface.md).

## Implication for a CW decoder (and digimodes)
A CW decoder needs the audio-tone envelope sampled at ≈100–250 Hz (a Goertzel at the CW pitch
+ element timing). Against that:

| Run it on… | Verdict |
|------------|---------|
| **Main CPU (RZ/A1)** | ❌ **No audio data exists here.** Only slow, passband-wide meters and ~tens-of-Hz scope frames — enough to sense "a signal is present," not to decode CW reliably (too slow, not tone-specific). Schematic-confirmed: codecs are on the DSP. |
| **DSP (TMS320C6745)** | ✅ **Right place** — the audio samples are here, and a CW decoder is tiny (easily fits 256 KB, trivial compute). **Gated** by needing the DSP firmware blobs + TI CCS toolchain (see `hardware.md`). |
| **PC / companion SBC** | ✅ USB audio → `fldigi`/PC CW decoder. Works today, no firmware risk. |

## Course correction for the modding plan
This refutes the earlier idea that a CW decoder is the natural *main-CPU* first feature: the
main CPU has nothing to decode. Signal-decode features (CW/FT8/FreeDV) all need audio, which is
**DSP-only** on this radio. Therefore:
- **On-radio MAIN-CPU firmware** → good for **UI / menu / CI-V / control** features (reachable,
  flashable, no audio needed). Not for decoders.
- **On-radio signal decoders** → belong on the **DSP** (feasible size-wise, but gated on the DSP
  blobs + toolchain) — the higher-effort path.
- **Pragmatic decoders (CW/FT8/FreeDV)** → **PC or companion SBC** over USB audio.
