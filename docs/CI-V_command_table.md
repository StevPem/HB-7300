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

### `0x16` subcommands `4F/50/56/57/58/65/66` — resolved from firmware

Each was traced to its get/set handler and leaf function. All write **DSP shadow
registers** (value + the `0x40` "push-to-DSP" dirty bit) in the DSP-filter module
(`0x200300xx`), confirming they are DSP/filter function controls.

| Sub | Firmware mechanism | Identification | Conf. |
|-----|--------------------|----------------|-------|
| 56 | per-(mode,filter) 2-value via `FUN_20027DEC`/`FUN_20027E0C`; `SHARP`/`SOFT` strings present | **IF filter shape SHARP/SOFT** (per mode & FIL1/2/3) | high |
| 57 | per-mode 3-value (`DAT_200306E0[mode]`), issues DSP command `0x11` via `FUN_20046BF0`; `Filter Type (HF)/(50M-)` strings | **DSP "Filter Type"** (per-mode filter preset) | med-high |
| 58 | per-mode 3-value, writes per-mode table (`DAT_2002F770+0x26A`) + DSP update | per-mode DSP filter parameter (3-state) | med |
| 65 | 1-bit: sets bit 3 of DSP reg `DAT_200306C4`, getter reads it back | DSP on/off function (1-bit) | med |
| 66 | on/off: sets reg bit `0x20`, triggers timed action `FUN_2003AA4C(8,100)` | DSP/audio on/off + triggered action | med |
| 50 | per-mode 2-value via callback (`FUN_2000CA08`→fn ptr, `FUN_200583B0(2)`) | per-mode DSP function toggle (2-state) | med |
| 4F | handler chain `0x2000CD46`(set)/`0x2000F7F2`(get); DSP toggle | DSP function toggle | low |

**Note:** mechanisms are firmware-confirmed; `56`/`57` map to the on-screen `SHARP/SOFT`
and `Filter Type` settings. The remaining five are DSP-filter-module toggles whose exact
product-menu label requires either Icom's authoritative `0x16` reference or the DSP command
set — the latter is the **layer-3 (DSP/FPGA) gap** noted in the roadmap, since labels like
these are defined by the DSP firmware's command numbers (e.g. the `0x11` seen for `0x57`).

#### Route (a) attempt — menu-label correlation for `0x58/0x65/0x66`

Traced the menu-side callbacks into a **function-ID dispatch table** (16-byte entries,
`{id, getter, id+1, setter}`): `0x58` is registered under internal item IDs `0x50/0x51`
(callbacks `FUN_200313C8`/`FUN_200314BC`), `0x65` under `0x52/0x53`
(`FUN_2003145C`/`FUN_20030FD0`). However, **no label `char*` appears anywhere near these
callbacks, getters, or the dispatch table** — the menu labels are **string-resource IDs
resolved at runtime by the OpenVG menu system**, not inline strings. So static `char*`
correlation terminates one hop short of a human label for `0x58/0x65/0x66`; naming them
needs the menu string-resource map (same resource-manager indirection documented in §7a)
or the DSP command reference. `0x56`/`0x57` remain the only two of the seven with a
firmware-anchored name.

#### Menu string-resource resolver — and refined `0x16` names

The menu label mechanism was reversed: each menu item is a static descriptor with a
**direct inline label `char*` at `+0x10`** (English) and a **Japanese label at `+0x1C`**,
tagged by a shared marker `0x20359E5C` at `+0x14`, with the **value-list at `+0x24`** and
flags at `+0x2C`. (Labels are plain strings, not runtime resource IDs; the per-item
*handler* field at `+0x28` is a runtime RAM/BSS pointer, so the CI-V→item binding is set
at runtime and cannot be followed statically.) Scanning this pattern yields **262 menu
items** (102 with value-lists) — see [`menu_labels.md`](menu_labels.md).

Reading the value-lists refines the earlier `0x16` guesses:

| Sub | Menu item | Value-list | Identification | Conf. |
|-----|-----------|-----------|----------------|-------|
| 56 | **Filter Type (HF)/(50M-)** | SHARP, SOFT | IF filter shape (per mode/filter) | high |
| 57 | **Filter** | FIL1, FIL2, FIL3 | IF filter # select (per mode; DSP cmd 0x11) | med-high |
| 58 | **[NOTCH] Switch (SSB)/(AM)** (candidate) | Auto, Manual, Auto/Manual | notch mode (3-state, per mode) — *candidate by 3-value/per-mode match* | med |
| 65 | — | — | 1-bit global DSP toggle (reg `DAT_200306C4` bit 3) — not statically linked to a label | low |
| 66 | — | — | on/off + triggered action (`FUN_2003AA4C`) — not statically linked | low |
| 50 | — | — | per-mode 2-value DSP toggle — not statically linked | low |
| 4F | — | — | DSP toggle — not statically linked | low |

`56`/`57` are now value-list-confirmed (correcting the earlier `0x57`="Filter Type" guess —
"Filter Type" is the SHARP/SOFT item = `0x56`; `0x57` is the FIL1/2/3 **Filter** selector).
`58` is a strong candidate (3-state per-mode matches **[NOTCH] Switch**). `65/66/50/4F`
could not be tied to a specific label because the item→handler binding is runtime-resolved;
the full label map is nonetheless available for any menu-driven setting.
