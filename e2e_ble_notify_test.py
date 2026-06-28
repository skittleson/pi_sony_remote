#!/usr/bin/env python3
"""
End-to-end BLE notify test client.

Run this on a Linux laptop to connect to the Pi's BLE notify service,
enable notifications, and print received filename events.

Usage:
  python3 e2e_ble_notify_test.py <PI_MAC_ADDRESS>

Example:
  sudo python3 e2e_ble_notify_test.py B8:27:EB:E5:8F:0C

The test runs for 60 seconds. Create a new .jpg file in /home/dietpi/downloads/
on the Pi during this time to trigger a notification.

Requires:
  - bluepy (pip3 install bluepy)
  - root or bluetooth group access to the local BLE adapter
  - Pi running a6400_ble_notify.py and discoverable via BLE
"""

import sys
import time

import bluepy.btle as btle

SERVICE_UUID = "12341000-1234-1234-1234-123456789abc"
CHAR_UUID = "2A6E"
TEST_TIMEOUT_SECONDS = 60

class NotifyDelegate(btle.DefaultDelegate):
    """Prints received BLE notifications."""

    def __init__(self):
        super().__init__()
        self.notifications = []

    def handleNotification(self, handle, data):
        filename = data.decode("utf-8", errors="replace")
        self.notifications.append(filename)
        print(f"NOTIFY received: {filename}")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <PI_MAC_ADDRESS>")
        print("Example: sudo python3 e2e_ble_notify_test.py B8:27:EB:E5:8F:0C")
        sys.exit(1)

    pi_mac = sys.argv[1]

    print(f"Connecting to Pi BLE at {pi_mac}...")

    try:
        with btle.Peripheral(pi_mac) as peripheral:
            delegate = NotifyDelegate()
            peripheral.withDelegate(delegate)

            service = peripheral.getServiceByUUID(SERVICE_UUID)
            char = service.getCharacteristics(CHAR_UUID)[0]

            print(f"Connected. Service {SERVICE_UUID}, Char {CHAR_UUID}")

            # Enable notifications via the CCCD descriptor (0x2902)
            print("Enabling notifications...")
            descriptors = char.getDescriptors()
            if descriptors:
                for desc in descriptors:
                    if str(desc.uuid).startswith("0x2902") or str(desc.uuid) == "2902":
                        desc.write(b"\x01\x00")
                        break
            else:
                print("WARNING: no CCCD descriptor found — notifications may not work")

            print(f"Listening for notifications ({TEST_TIMEOUT_SECONDS}s)...")
            print("Create a new .jpg file in /home/dietpi/downloads/ on the Pi now.")

            start = time.time()
            while time.time() - start < TEST_TIMEOUT_SECONDS:
                peripheral.waitForNotifications(1.0)

            print(f"\nTest complete. Received {len(delegate.notifications)} notification(s).")

            if delegate.notifications:
                print("Notifications received:")
                for fn in delegate.notifications:
                    print(f"  - {fn}")
                # Check for duplicates
                seen = set()
                dupes = [fn for fn in delegate.notifications if fn in seen or seen.add(fn)]
                if dupes:
                    print(f"  WARNING: duplicate notifications detected: {dupes}")
                    sys.exit(1)
                sys.exit(0)
            else:
                print("No notifications received — was a new .jpg file created?")
                print("Ensure the Pi's BLE service is running:")
                print("  sudo systemctl status a6400-ble-notify")
                sys.exit(1)

    except btle.BTLEDisconnectError as e:
        print(f"Disconnected: {e}")
        sys.exit(1)
    except btle.BTLEException as e:
        print(f"BLE error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
