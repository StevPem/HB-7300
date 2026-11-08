# RX signal access on the main CPU — what a decoder can (and can't) see

> **CORRECTION (via jeskko/ic7300-homebrew).** The conclusion below — "no audio tap on the main
> CPU" — is **wrong**. The main CPU *does* receive **demodulated RX audio** from the DSP over an
> SSIF/I2S link: the `DX_REC L` stream is kept in a **48 kHz ring at `0x203FBDC0`** (feeding the SD-card
> QSO recorder and the audio scope), and `DX_FMT L` carries per-mode demod output too. There is also a
> **TX audio injection path** (`DR_AF L`, used for voice-memory playback at `0x20067458`). I missed these
> by examining only the metering and the SCIF5 DSP-command link, not the SSIF audio channel. Net: an
> on-radio **CW / SSTV / FT8-RX decoder is feasible on the main CPU** — jeskko's SDK already ships a
> working **SSTV receiver** app that taps the 48 kHz ring (decimated to 12 kHz) via a loader hook, and
> TX digimodes are feasible in principle via the `DR_AF` path + CI-V PTT. See their `notes/dsp-protocol.md`
> and `sdk/`.


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
