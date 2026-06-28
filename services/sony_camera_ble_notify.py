#!/usr/bin/env python3
"""
Sony a6400 BLE notify server — NOT SUPPORTED ON PI ZERO W.

The BCM43430A1 chip in the Pi Zero W does not support BLE peripheral
advertising. Every attempt to advertise fails with:

  Failed to add advertisement: Invalid Parameters (0x0d)

This is a confirmed hardware limitation of the BCM43430A1. The Pi Zero W
can act as a Bluetooth Classic (BR/EDR) peripheral (RFCOMM works fine),
but BLE peripheral mode is non-functional.

For BLE notifications, use a Raspberry Pi 3 or later with a chipset that
supports BLE peripheral advertising (e.g., BCM43430C0 on the Pi 3, or
BT720 on the Pi 5).

If you have a newer Pi, install bluezero and use the bluezero approach:
  pip3 install bluezero
  # Then run sony_camera_ble_notify.py (see commit history for the working version)
"""

import sys

def main():
    print(__doc__)
    sys.exit(1)

if __name__ == "__main__":
    main()
