# MAIN CPU ↔ DSP (TMS320C6745) interface

How the RZ/A1 main CPU controls and loads the IF-DSP. Reversed from the main-CPU firmware;
the DSP's own code is a separate blob (not in the MAIN update file) — this documents the
**bridge**, which is the entry point for any DSP-side work.

## Control path (MAIN → DSP)

A setting change (from a menu item or a CI-V `0x16`/`0x14` command) flows through:

```
FUN_20046BF0(cmd_id, value)                      // DSP-parameter setter
  ├─ look up cmd in the 25-entry shadow table @ RAM 0x20199FB0 (0x1C bytes/entry)
  ├─ bounds-check value (type 1 = u8, type 2 = u16) against entry.lo/.hi
  ├─ write it into the DSP shadow buffer @ RAM 0x203DE732..0x203DE74C
  └─ call entry.apply_fn (+0x18)  ──►  enqueue a DSP command (priority queue, ≤10)
                                        + set "pending" dirty bit 0x203902D7 (|0x40)
                                           │
                            DSP service task drains the queue  ──► serial link
                                           (DSPCK/DSPR/FRM/BCLK/DSTB → TMS320C6745)
```

Each shadow-table entry: `{u32 target_ptr, u8 type, …, u8 lo @+0xC, u8 hi @+0x10, …, fn apply @+0x18}`.
There are **8 distinct apply functions** (trampolines into the transport core at ~`0x20045A14`),
which insert the parameter into the command queue rather than touching MMIO directly.

## The 25 controllable DSP parameters

Shadow bytes are contiguous at `0x203DE732`–`0x203DE74C`. Ranges hint at meaning
(0–1 = on/off, small ranges = enums, wide = levels/bandwidths):

| # | shadow addr | type | range | apply fn |
|---|-------------|------|-------|----------|
| 1 | 0x203DE732 | u8 | 0–255 | 0x20045ECC |
| 2 | 0x203DE733 | u8 | 0–255 | 0x20045ECC |
| 3 | 0x203DE734 | u8 | 0–255 | 0x20045ECC |
| 4 | 0x203DE735 | u8 | 0–255 | 0x20045F18 |
| 5 | 0x203DE736 | u8 | 0–1 | 0x20045EC8 |
| 6 | 0x203DE737 | u8 | 0–10 | 0x20045EC8 |
| 7 | 0x203DE738 | u8 | 0–1 | 0x20045EC8 |
| 8 | 0x203DE739 | u8 | 0–255 | 0x20045EC8 |
| 9 | 0x203DE73A | u8 | 0–255 | 0x20045F24 |
| 10 | 0x203DE73C | **u16** | 44–132 | 0x20045F38 |
| 11 | 0x203DE73E | u8 | 0–1 | 0x20045EC8 |
| 12 | 0x203DE73F | u8 | 0–255 | 0x20045EC8 |
| 13 | 0x203DE740 | u8 | 0–9 | 0x20045EC8 |
| 14 | 0x203DE741 | u8 | 0–255 | 0x20045EC8 |
| 15 | 0x203DE742 | u8 | 0–15 | 0x20045EC8 |
| 16 | 0x203DE743 | u8 | 0–255 | 0x20045EC8 |
| 17–20 | 0x203DE744–747 | u8 | 0–2 | 0x20045EC8 |
| 21 | 0x203DE748 | u8 | 0–255 | 0x20045F58 |
| 22 | 0x203DE749 | u8 | 0–255 | 0x20045F5C |
| 23 | 0x203DE74A | u8 | 0–20 | 0x20045EC8 |
| 24 | 0x203DE74B | u8 | 0–3 | 0x20045EC8 |
| 25 | 0x203DE74C | u8 | 20–130 | 0x20045F60 |

(Index 0 is a null/sentinel entry.) These are the knobs the DSP exposes — filter/NR/NB/notch/
AGC-class settings; command `0x11` is additionally mode-indexed via `FUN_200463D4`.

## DSP firmware version check & load
`FUN_200A94C8` compares the DSP's running identity (version word + several 4-byte fields) against
the expected values. On mismatch it drives the **"DSP/FPGA firmware is wrong"** / **"Updating
DSP/FPGA firmware"** flow and shows the **"DSP Program:" / "DSP Data:"** version dialog; the update
path then loads the matching Program + Data blobs into the DSP. The DSP code/coefficients
("Program"/"Data") live in the flash regions beyond the MAIN update file.

## What this enables for modding
- This is the **complete DSP control surface** from the main CPU: 25 parameters, their types,
  ranges, and the command/queue transport. Custom main-CPU code can drive the DSP through
  `FUN_20046BF0` (or the queue directly) using these IDs.
- It does **not** let you run new code *on* the DSP — that needs the DSP Program/Data blobs and
  the C6745 toolchain (see `hardware.md`). But it is the map you'd build a DSP-side feature against.
- Physical transport (the McBSP/serial register writes to the C6745) is the queue-drain task,
  one layer below the apply functions — the next detail to pin down if driving the DSP directly.
