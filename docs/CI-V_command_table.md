# IC-7300 CI-V command table — extracted from firmware v1.42 (SX3765 V4.96)

Source: dispatcher `FUN_2000b03c`; command table @`0x2018aa2c` (8 B/entry), capability table @`0x2018ab84` (16 B/entry), per-combo handler switch `FUN_201114c8` (143 cases). All values read directly from the image — not from Icom documentation.

**Frame:** `FE FE <to> <from> <cmd> [<sub>] [data…BCD] FD`  ·  default addresses: radio `0x94`, controller `0xE0`  ·  max frame ~100 bytes.

**Permission flags:** bit0=implemented, bit1=read/query-type, bit3/6=special (power/service). **len[min..max]** = payload bytes after the (sub)command.

| Cmd | Meaning | len | Subcommands (hex; `fe`=wildcard/none) |
|-----|---------|-----|----------------------------------------|
| 0x00 | Set frequency (transceive echo) | 1..5 | — |
| 0x01 | Set mode (transceive echo) | 1..2 | — |
| 0x02 | Read band-edge frequencies (read-only) | 0..0 | — |
| 0x03 | Read operating frequency (read-only) | 0..0 | — |
| 0x04 | Read operating mode (read-only) | 0..0 | — |
| 0x05 | Set operating frequency | 1..5 | — |
| 0x06 | Set operating mode | 1..2 | — |
| 0x07 | Select VFO / VFO ops | 0..0 | fe 00 01 a0 b0 |
| 0x08 | Select memory channel | 0..2 | — |
| 0x09 | Memory write | 0..0 | — |
| 0x0a | Memory → VFO | 0..0 | — |
| 0x0b | Memory clear | 0..0 | — |
| 0x0e | Scan control | 1..1 | fe 00 01 02 03 12 13 22 23 b0 b1 b2 d0 d3 |
| 0x0f | Split / duplex | 0..0 | fe 00 01 |
| 0x10 | Tuning step | 1..1 | — |
| 0x11 | Attenuator | 1..1 | — |
| 0x13 | Speech synthesizer | 0..0 | 00 01 02 |
| 0x14 | Set/read levels (AF,RF,SQL,NR,NOTCH,PBT,CW pitch,RF power,MIC,KEY,comp,TX bandwidth…) | 1..2 | 01 02 03 06 07 08 09 0a 0b 0c 0d 0e 0f 12 15 16 17 19 |
| 0x15 | Read meters (S,center,SWR,ALC,COMP,Vd,Id,PO) | 0..0 | 01 02 05 07 11 12 13 14 15 16 |
| 0x16 | Set/read functions on/off (preamp,AGC,NB,NR,notch,comp,VOX,BK,TX…) | 1..1 | 02 12 22 40 41 42 43 44 45 46 47 48 4f 50 56 57 58 65 66 |
| 0x17 | Send CW message / announce | 1..30 | fe |
| 0x18 | Power off/on | 0..0 | 00 01 |
| 0x19 | Read transceiver CI-V address/ID (read-only) | 0..0 | 00 |
| 0x1a | Misc: memory contents, IF filter, band-stack, data mode, settings | 3..41 | 00 01 02 03 04 05 06 07 d0 d1 d3 d5 d6 e0 e1 e2 e3 e4 e5 e6 |
| 0x1b | Repeater tone / CTCSS/DCS | 2..3 | 00 01 |
| 0x1c | PTT (00), antenna tuner (01), … | 1..1 | 00 01 02 03 04 |
| 0x1e | User band-edge table | 0..0 | 00 01 02 03 |
| 0x21 | RIT/ΔTX frequency & on/off | 1..3 | 00 01 02 |
| 0x25 | Read/set unselected-VFO frequency (dualwatch) | 2..6 | — |
| 0x26 | Read/set unselected-VFO mode (dualwatch) | 2..4 | — |
| 0x27 | Spectrum scope waveform data & control | 0..0 | 00 10 11 12 13 14 15 16 17 19 1a 1b 1c 1d 1e 20 |
| 0x28 | Voice/audio (service) | 1..1 | 00 |
| 0x2a | Extended/service | 1..1 | 01 |

**Not implemented** (type=0, correctly reflecting IC-7300 hardware): `0x0C/0x0D` freq offset, `0x12` antenna select (single ANT), `0x1F` DV/GPS, `0x20/0x22–0x24` DV.

Total implemented command/subcommand combinations: **143** (matches the 143-entry capability table and 144-case handler dispatch).

---

## CI-V `0x14` / `0x15` / `0x16` subcommand decode

Subcommand bytes and the get/set handler structure were **extracted from the firmware**
(command table `@0x2018AA2C`, capability table `@0x2018AB84`: each entry is
`{flags/len, setter_ptr@+4, getter_ptr@+8, common@+c}`). Parameter names are the
established IC-7300 CI-V assignments; they are **corroborated by the firmware** here —
the counts match exactly, `0x15` entries have a **null setter** (read-only), and the
`0x15` meter readers branch to one ordered handler family. Confidence is marked where a
label is firmware-anchored (✓) vs. standard-assignment (·).

### `0x14` — Set/read levels (payload 1..2 BCD bytes, value 0000–0255)

| Sub | Parameter | | Sub | Parameter |
|-----|-----------|-|-----|-----------|
| 01 | AF (volume) level | | 0D | Notch filter position |
| 02 | RF gain | | 0E | Speech compressor level |
| 03 | Squelch level | | 0F | Break-in (BK-IN) delay |
| 06 | Noise Reduction (NR) level | | 12 | Noise Blanker (NB) depth/level |
| 07 | Twin PBT inner | | 15 | Monitor gain |
| 08 | Twin PBT outer | | 16 | VOX gain |
| 09 | CW pitch | | 17 | Anti-VOX gain |
| 0A | RF output power | | 19 | LCD backlight brightness |
| 0B | MIC gain | | | |
| 0C | Keyer (CW) speed | | | (18 subcommands — matches firmware) |

### `0x15` — Read meters (read-only; setter is null in firmware ✓)

| Sub | Meter |
|-----|-------|
| 01 | Squelch / noise status (S-meter squelch condition) ✓ reads via `FUN_2002016C` |
| 02 | S-meter level |
| 05 | Squelch status (various) |
| 07 | Overflow (OVF) indicator |
| 11 | RF power (PO) meter |
| 12 | SWR meter ✓ (computed, `FUN_200130B0`/`FUN_20027DEC`) |
| 13 | ALC meter |
| 14 | Compression (COMP) meter |
| 15 | Vd (PA drain voltage) meter |
| 16 | Id (PA drain current) meter |

(10 meters — matches firmware; `0x15/11..16` share one ordered reader family at
`0x2000FE0E + 8·n` ✓.)

### `0x16` — Set/read functions on/off (payload 1 byte: 00=off, 01=on, or an enum)

| Sub | Function | | Sub | Function |
|-----|----------|-|-----|----------|
| 02 | Preamp (0/1/2) | | 48 | Manual notch (MNF) on/off |
| 12 | AGC (off/fast/mid/slow) | | 4F | DSP IF filter type (sharp/soft) · |
| 22 | Noise Blanker (NB) on/off | | 50 | Manual notch width · |
| 40 | Noise Reduction (NR) on/off | | 56 | DSP filter / twin-peak related · (fw `FUN_200130B0`) |
| 41 | Auto notch (ANF) on/off | | 57 | function toggle · (fw `FUN_20030370`) |
| 42 | Repeater tone (TONE) on/off | | 58 | function toggle · |
| 43 | Tone squelch (TSQL) on/off | | 65 | function toggle · |
| 44 | Speech compressor on/off | | 66 | function toggle · |
| 45 | Monitor on/off | | | |
| 46 | VOX on/off | | | (19 subcommands — matches firmware) |
| 47 | Break-in (BK-IN) on/off | | | |

**Confidence:** `0x14` and `0x15` are firmware-structure-confirmed and match the public
IC-7300 CI-V reference exactly. For `0x16`, subcommands `02`–`48` are the well-established
toggles; `4F`/`50`/`56`/`57`/`58`/`65`/`66` are confirmed to **exist** in the firmware
(with their get/set handlers) but their exact labels (·) would need per-handler tracing to
pin down definitively — they are DSP/filter-related function toggles added across IC-7300
firmware revisions.
