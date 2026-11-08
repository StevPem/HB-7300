# CW decoder — a homebrew app for the IC-7300

A Morse (CW) receive decoder that runs **on the radio** as a homebrew app, using the
[jeskko/ic7300-homebrew](https://github.com/jeskko/ic7300-homebrew) SDK (loader ABI v4). It taps
the radio's 12 kHz demodulated RX audio, locks onto the CW tone, and scrolls decoded text on a
full-screen canvas over the normal UI.

This is a **contribution offered to that SDK** (it's the natural next example app after `sstv-rx`,
and a CW decoder didn't exist yet). It is built and verified here against their real headers; it has
**not** run on hardware — see their safety warning before flashing anything.

## What it does
- **Goertzel** tone detector at the configured CW pitch → adaptive on/off threshold (decaying
  min/max envelope + hysteresis) → **self-timing Morse** classification (adaptive dit length, so it
  tracks ~7–40 WPM without a speed setting) → ASCII.
- Full-screen UI: a live tone/threshold meter, estimated **WPM** and pitch, and scrolling decoded
  text. Tap the top strip to cycle pitch **500/600/700/800 Hz**; **EXIT** or the on-screen **✕** quits.
- Integer/float DSP only, ~**0.2 MFLOP/s** at 12 kHz (64-sample frames) — well under 1% of the
  Cortex-A9, far lighter than the working SSTV app.

## Files
```
cw_core.h / cw_core.c   portable decoder (Goertzel + timing + Morse table); the only radio dep is hb_cosf
main.c                  the app: audio tap + canvas UI (hb/audio.h, hb/gfx.h, hb/input.h)
host_test.c             synthesises keyed CW and decodes it — proves the algorithm on a PC
```

## Build & run (with the jeskko SDK)
Copy this folder into `sdk/examples/cw-rx/` of a jeskko/ic7300-homebrew checkout, then from its repo root:
```bash
python3 sdk/tools/build_app.py -o CWRX.BIN sdk/examples/cw-rx/main.c sdk/examples/cw-rx/cw_core.c
# put CWRX.BIN in \homebrew\ on the SD card; launch: MENU > SET > SD Card > Homebrew Apps > CWRX
```
Try it in their QEMU emulator first (the fake DSP can play a WAV into the RX slot, `RZA1H_AF_FILE`).

## Host self-test (no radio)
```bash
cc -DCW_HOST -O2 -o cw_test host_test.c cw_core.c -lm
./cw_test 22 8 "CQ CQ DE HB9XYZ/P K"      # args: WPM, SNR dB, message
# -> decoded: "CQ CQ DE HB9XYZ/P K"  (exact copy at 13–28 WPM, down to ~6 dB SNR in this model)
```

## Using it on the air
Tune a CW signal in **CW/CW-R** so its beat note sits at your **CW PITCH** (match the app's pitch to
the radio's PITCH setting), with a reasonably narrow filter. The decoder adapts to speed automatically.

## Limitations / honest notes
- RX decode only (no TX). Straight, well-formed CW decodes best; heavy QRM/QSB, very weak signals, or
  bad fists degrade it, like any tone decoder.
- Pitch is matched by the four presets; if your CW PITCH is elsewhere, the nearest preset usually still
  captures the tone (the Goertzel bin is broad), but exact match is best.
- Not tested on hardware. Frame timing, audio-block loss, and touch behaviour are emulator-validated
  only. Treat on-air use as experimental.
- Targets firmware v1.42 via the loader ABI, same as the rest of the SDK.
