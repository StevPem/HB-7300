## Add a CW (Morse) receive decoder example app

This adds `cw-rx`, a Morse receive decoder that runs on the radio, in the same
style as `sstv-rx`. It taps the 12 kHz demodulated RX audio, locks onto the CW
tone, and scrolls decoded text on a full-screen canvas over the normal UI.

### How it works
- **Goertzel** tone detector at the configured CW pitch
- adaptive on/off threshold (decaying min/max envelope + hysteresis)
- **self-timing Morse** classification — adaptive dit length, so it tracks
  ~7–40 WPM with no speed setting — → ASCII
- Full-screen UI: live tone/threshold meter, estimated WPM and pitch, scrolling
  text. Tap the top strip to cycle pitch 500/600/700/800 Hz; EXIT or the
  on-screen ✕ quits.
- Integer/float DSP only, ~0.2 MFLOP/s at 12 kHz (64-sample frames) — well under
  1% of the Cortex-A9, lighter than `sstv-rx`. The only radio dependency in the
  core is `hb_cosf`.

### Files
```
cw_core.h / cw_core.c   portable decoder (Goertzel + timing + Morse table)
main.c                  the app: audio tap + canvas UI (hb/audio,gfx,input)
host_test.c             synthesises keyed CW and decodes it — proves it on a PC
```

### Build
```
python3 sdk/tools/build_app.py -o CWRX.BIN sdk/examples/cw-rx/main.c sdk/examples/cw-rx/cw_core.c
```

### Verification
- Host self-test (`cc -DCW_HOST -O2 -o cw_test host_test.c cw_core.c -lm`) gives
  an exact copy at 13–28 WPM, down to ~6 dB SNR in the synthetic model.
- `cw_core.c` and `main.c` compile clean against the SDK headers (ABI v4).

### Honest status
**Not run on hardware.** Frame timing, audio-block handling, and touch behaviour
are reasoned against the SDK/emulator only — I don't own a '7300 to flash. Happy
to iterate on anything, and glad to have a hardware owner smoke-test it before
merge. RX decode only (no TX).
