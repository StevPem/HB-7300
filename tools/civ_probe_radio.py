#!/usr/bin/env python3
"""On-radio dynamic naming of CI-V 0x16 subcommands that can't be resolved statically.

The IC-7300 menu item -> setting binding is built at boot in RAM, so a few CI-V 0x16
subcommands can't be tied to a menu label by static analysis. The practical dynamic test,
for anyone with the radio: READ each subcommand, then watch which front-panel / menu
setting the radio reports — that empirically names it.

Connects to the IC-7300 over its USB CI-V port (a CP210x serial device). Default radio
CI-V address 0x94, controller 0xE0. SAFE: this only sends READ frames (no writes), so it
cannot change radio state. To toggle a setting for observation, pass --toggle (asks first).

Usage:
    python3 civ_probe_radio.py --port /dev/ttyUSB0 --baud 115200
    python3 civ_probe_radio.py --port COM5 --toggle        # also sends off/on writes
"""
import argparse, sys, time
try:
    import serial
except ImportError:
    sys.exit("pip install pyserial")

RADIO=0x94; CTRL=0xE0
UNKNOWN_SUBS=[0x4F,0x50,0x58,0x65,0x66]   # the ones needing dynamic naming
NAMED={0x56:"Filter Type (SHARP/SOFT)",0x57:"Filter (FIL1/FIL2/FIL3)"}

def frame(cmd, data=b""):
    return bytes([0xFE,0xFE,RADIO,CTRL,cmd])+bytes(data)+b"\xFD"

def txrx(ser, payload, wait=0.25):
    ser.reset_input_buffer(); ser.write(payload); time.sleep(wait)
    return ser.read(ser.in_waiting or 1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",required=True); ap.add_argument("--baud",type=int,default=115200)
    ap.add_argument("--toggle",action="store_true")
    a=ap.parse_args()
    ser=serial.Serial(a.port,a.baud,timeout=0.3)
    print(f"IC-7300 CI-V on {a.port}@{a.baud}. Radio=0x94 Ctrl=0xE0.\n")
    for sub in UNKNOWN_SUBS:
        r=txrx(ser, frame(0x16,[sub]))
        print(f"0x16/{sub:02X}  READ -> {r.hex(' ')}")
        if a.toggle:
            ans=input(f"   toggle 0x16/{sub:02X}? watch the radio screen [y/N] ").strip().lower()
            if ans=="y":
                for v in (0x00,0x01):
                    txrx(ser, frame(0x16,[sub,v]))
                    print(f"     wrote {v:02X}; note what changed on the radio, then press Enter"); input()
    ser.close()
    print("\nMap each subcommand to the setting that changed. 0x56/0x57 are already named:",
          NAMED)

if __name__=="__main__":
    main()
