# SPI-NOR flash driver (W25 via RZ/A1 SPIBSC) — the reflash write primitive

Reversed from the update module. The firmware is stored in, and runs XIP from, a Winbond **W25**
SPI-NOR flash on the RZ/A1 **SPIBSC0** controller (base **`0x3FEFA000`**), memory-mapped at
`0x18000000`. To write it, the driver switches SPIBSC from memory-mapped read to SPI command
mode and drives erase/program directly. This is the primitive any reflash needs.

## SPIBSC registers used (base `0x3FEFA000`)
| Offset | Reg | Use here |
|--------|-----|----------|
| +0x20 | SMCR | trigger (`1`=exec, `0x101`=+address, `0x103`=+data write/continue, `3`=final; `5`=read) |
| +0x24 | SMCMR | command, in bits [23:16] (e.g. `0x060000`=WREN) |
| +0x28 | SMADR | flash address |
| +0x30 | SMENR | enable (`0x4000` cmd-only, `0x4700` cmd+addr, `0xF`/`8` data width) |
| +0x40 | SMWDR0 | write data word |
| +0x48 | CMNSR | status; polled done-bit via `FUN_20360B44` |

## SPI-NOR command set (Winbond W25)
| Cmd | SMCMR | Meaning | Routine |
|-----|-------|---------|---------|
| `0x06` | `0x060000` | WREN (write enable) | prefix to every write |
| `0x01` | `0x010000` | WRSR = 0 (clear block protection / unprotect) | `FUN_20024BB8` (setup) |
| `0x05` | `0x050000` | RDSR (read status) | `FUN_20024904` / `FUN_2002497C` |
| `0x02` | `0x020000` | **Page Program** (256 B) | `FUN_20024A60` |
| `0xD8` | `0xD80000` | **64 KB Block Erase** | `FUN_20024BB8` |

## Routines
- **`FUN_20024850`** — SPIBSC init: configure CMNCR/DRCR/… and enter command mode.
- **`FUN_20024BB8(start, end)`** — unprotect (WREN+WRSR0), then **erase** in **64 KB blocks**:
  `WREN → SMCMR=0xD80000, SMADR=addr, exec`, wait WIP, `addr += 0x10000` until `end`.
- **`FUN_20024A60(flash_addr, buf, len)`** — **page program**: `WREN → PP(0x02) with addr`, stream
  data words to SMWDR0 in **256-byte pages**, then wait WIP. **Skips all-`0xFF` words** (erased
  flash reads `0xFF`, so unchanged words aren't reprogrammed).
- **`FUN_20024904`** — wait-write-complete: RDSR poll until **WIP (bit0) = 0**.
- **`FUN_2002497C`** — wait-write-enabled: RDSR poll until **WEL (bit1) = 1**.
- **`FUN_20024CD0`** — restore SPIBSC to memory-mapped **XIP read** mode (CMNCR ← `DAT_20025020`).

## What this gives the modding project
A fully understood **write primitive**: *erase 64 KB blocks, then program 256 B pages* over
SPIBSC0, with status polling and 0xFF-skip. Combined with "no signature" (`modding-feasibility.md`)
and the LZSS repack tooling, this is the mechanism to lay a modified image onto the flash.

## Critical hazards
- **Self-flash / XIP hazard:** the CPU runs XIP from the *same* flash being erased/programmed.
  During erase/program, memory-mapped reads from `0x18000000` return garbage, so the active write
  code and its data **must be RAM-resident** and interrupts disabled (the driver calls
  `disableIRQinterrupts()` around mode switches). Getting this wrong hangs or bricks the radio.
- **Erase granularity is 64 KB** — you must preserve/rewrite whole 64 KB blocks.
- **Brick risk / recovery:** combine with the stage-2 dual-image failsafe (see the main report);
  prove a recovery path before any real write.

## Still open for the full container
The write *mechanism* is solved; the *container sealing* is not fully pinned: the 7×u32 header
table's exact fields and where the per-image CRC32/MD5 integrity values are stored (the simple
"whole-payload CRC/MD5" hypotheses did not match — it is per-image, matching the multi-image
"Partial" container). Those must be reproduced for the updater to accept a modified `.dat`.
