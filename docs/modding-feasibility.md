# Custom-firmware feasibility — update & integrity analysis (Step 1)

**Verdict: GO (cryptographically).** The IC-7300 firmware update has **no digital-signature
verification**. Integrity is enforced only by **non-keyed checksums (CRC32) and an MD5 hash**,
both of which a modifier can recompute. There is therefore no cryptographic barrier to
flashing modified firmware. (This is the go/no-go answer — it does **not** make the project
easy or safe; see caveats.)

## Why: no asymmetric crypto exists in the image
Verifying a signature requires asymmetric primitives (RSA modexp or ECC point math) **and** a
public key. An exhaustive search of the 3.5 MB main-CPU image found **none**:

| Primitive | Result |
|-----------|--------|
| RSA public-key modulus (1024/2048-bit) | **absent** (the `0x10001` constants sit in low-entropy, non-key contexts; no modexp) |
| ECC curves (NIST P-256, secp256k1, Ed25519) | **absent** (no curve/field/base-point constants) |
| SHA-256 / SHA-512 | **absent** (no round constants) |
| **MD5** | **present** — full init vector `67452301 efcdab89 98badcfe 10325476` @`0x38280`; round fn `FUN_2003C890` |
| **CRC32** | **present** — poly `0xEDB88320` + lookup table @`0x33BFDC` (also used by the bundled libpng) |

MD5 and CRC32 are **keyless**: anyone can recompute them over modified data. They detect
*accidental* corruption, not *intentional* modification. No key ⇒ no signature ⇒ no crypto lock.

## Update mechanism (reversed)
- Firmware is updated from a **`.dat` file on the SD card** (FAT); the UI shows
  "Updating MAIN CPU firmware." and "Updating DSP/FPGA firmware." — **MAIN-CPU and DSP/FPGA
  images are flashed separately**.
- **File format check** (`FUN_200253F4` → `FUN_200247E4`): start magic **`3wfU`** (`0x55667733`),
  **three 4-byte model-ID fields**, and a 2-byte **end marker `7e`** (`0x6537`). Format/model
  gating only — no hash or signature here.
- **Container header** (this file): `3wfU` + version string `3.112.003.16` + a **7×u32 table**
  (region sizes/offsets; see the main report), image begins at file `0x2C` → flash `0x18000000`.
- **Payload**: LZSS-compressed per region (depacker in `tools/`).

## Recovery / brick-risk
The stage-2 loader selects between firmware images by comparing a version string
(`memcmp("SX3765 V1.00-003", flash 0x187F0000)` → load `0x18400000` **or** `0x18010000`) — i.e.
a **dual-image / failsafe selection**, so a known-good loader can fall back. This *reduces*
(does not eliminate) brick risk. A safe modding loop must still prove recovery before writing.

## What this does NOT mean (honest caveats)
Cryptographically open ≠ easy or safe:
- **Bricking** — a bad MAIN-CPU flash can disable the radio; confirm the recovery path on
  hardware first.
- **Repack work** — must LZSS-recompress, fix the 7×u32 header, and recompute CRC32/MD5 so the
  updater accepts the image (toolchain to be built & proven on a byte-identical rebuild first).
- **DSP/FPGA gap** — real DSP features (CW/FT8 decode) need the signal path, which lives in the
  separate DSP/FPGA images (not in this file). This analysis only clears the MAIN-CPU updater.
- **RF compliance** — modifying TX firmware can affect spurious/out-of-band emissions; keep it
  type-compliant and legal for your licence.

## Next steps (unchanged order, now unblocked)
1. ✅ **Update/integrity/recovery path** — done here: no signature; CRC32+MD5; dual-image failsafe.
2. Prove a **safe flash + recovery** loop on hardware.
3. Build & prove the **repack toolchain** (LZSS + header + CRC32/MD5 fixup) on a byte-identical rebuild.
4. Map the **RX audio/data hooks** on the main CPU.
5. **Code-injection** framework (free space + RTOS task hook + OpenVG menu UI).
6. First feature — **CW decoder** before FT8.

Remaining to pin down for step 3: the exact routine that computes/verifies the per-region
CRC32/MD5 and where those values are stored (header 7×u32 vs per-image trailer), and the
low-level flash erase/program driver.
