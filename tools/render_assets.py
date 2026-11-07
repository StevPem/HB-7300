#!/usr/bin/env python3
"""Render the uncompressed 8-bpp grayscale UI bitmaps from IC-7300 flash.

The resource bank (flash 0x18250000+) holds 8-bpp grayscale images (alpha/intensity
masks the OpenVG renderer blits in a chosen color). Each asset's byte length equals
the gap to the next resource pointer; width is recovered by row autocorrelation.
Two confirmed, directly-renderable assets:
    0x18250000  36 x 33   circular dial/ring icon  (36*33 = 1188 bytes exactly)
    0x182504A4  156 x 44  letterform/logo glyphs

NOTE: this renders Icom UI artwork from YOUR OWN firmware for study; do not redistribute
the output. The large high-entropy assets are NOT bitmaps - they are OpenVG vector data.

Usage: python3 render_assets.py ic7300_firmware.dat   (needs Pillow)
"""
import sys
try:
    from PIL import Image
except ImportError:
    sys.exit("pip install pillow")

FLASH_BASE = 0x18000000
HDR = 0x2c  # .dat header: file offset 0x2c maps to flash 0x18000000

ASSETS = [(0x18250000, 36, 33, "dial_36x33.png"),
          (0x182504A4, 156, 44, "banner_156x44.png")]

def main(path):
    d = open(path, "rb").read()
    for flash, w, h, name in ASSETS:
        off = flash - FLASH_BASE + HDR
        img = Image.frombytes("L", (w, h), d[off:off + w * h])
        scale = max(1, 900 // max(w, h))
        img.resize((w * scale, h * scale), Image.NEAREST).save(name)
        print(f"wrote {name}  ({w}x{h}, 8bpp, flash 0x{flash:08x})")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
