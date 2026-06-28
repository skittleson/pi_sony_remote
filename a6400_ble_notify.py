#!/usr/bin/env python3
"""
Sony a6400 BLE notify server.

Monitors /home/dietpi/downloads/ for new JPEG files and sends a BLE
notification to any subscribed client with the filename (e.g. "00002.jpg").

Single-threaded: the main loop calls bluepy's waitForNotifications(2.0) to
yield for BLE events, then checks for new files on each iteration.

Requires root (or bluetooth group) to access the BLE controller.
"""

import signal
import logging
import os
import time

import bluepy.btle as btle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOWNLOAD_DIR = "/home/dietpi/downloads"
POLL_INTERVAL_SECONDS = 2.0

# Custom 128-bit UUIDs (generated, no collision risk with standard profiles)
SERVICE_UUID = "F000A001-0451-4000-B000-000000000000"
CHAR_UUID = "F000A002-0451-4000-B000-000000000000"

# ---------------------------------------------------------------------------
# Logging setup (timestamped to stdout, captured by systemd journal)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("a6400-ble-notify")

# ---------------------------------------------------------------------------
# GATT definitions
# ---------------------------------------------------------------------------

class NotifyCharacteristic(btle.Characteristic):
    """Notify characteristic that emits the filename when a new file appears."""

    def __init__(self):
        super().__init__(
            uuid=CHAR_UUID,
            properties=btle.CHAR_PROP_NOTIFY,
            value=b"",
        )

    def onSubscribe(self, handle, maxValue):
        log.info("client subscribed (handle=%s, max_value=%d)", handle, maxValue)

    def onUnsubscribe(self, handle):
        log.info("client unsubscribed (handle=%s)", handle)


class NotifyService(btle.Service):
    """BLE GATT service containing the notify characteristic."""

    def __init__(self):
        super().__init__(uuid=SERVICE_UUID)
        self.characteristics = [NotifyCharacteristic()]

# ---------------------------------------------------------------------------
# File monitoring
# ---------------------------------------------------------------------------

def get_jpg_files(directory):
    """Return a set of .jpg filenames currently in *directory*."""
    try:
        return {
            name for name in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, name))
            and name.lower().endswith((".jpg", ".jpeg"))
        }
    except OSError:
        return set()

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    log.info("starting BLE notify server (dir=%s, poll=%ss)", DOWNLOAD_DIR, POLL_INTERVAL_SECONDS)

    peripheral = btle.Peripheral()
    peripheral.addService(NotifyService())
    peripheral.startAdvertising()

    # Grab a reference to the characteristic for sending notifies
    service = peripheral.getServiceByUUID(SERVICE_UUID)
    char = service.getCharacteristics(CHAR_UUID)[0]

    log.info("BLE advertising started, service %s, characteristic %s", SERVICE_UUID, CHAR_UUID)

    notified = set()  # filenames we have already notified about

    # ------------------------------------------------------------------
    # Signal handling — graceful shutdown
    # ------------------------------------------------------------------

    def _shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        log.info("received %s — shutting down", sig_name)
        try:
            peripheral.stopAdvertising()
            peripheral._stopNotifying()
        except Exception:
            pass
        log.info("BLE peripheral stopped")
        os._exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # ------------------------------------------------------------------
    # Main event loop
    # ------------------------------------------------------------------

    while True:
        # Yield control to bluepy so BLE events (subscribe/unsubscribe)
        # can be processed. The timeout doubles as the polling interval.
        peripheral.waitForNotifications(POLL_INTERVAL_SECONDS)

        current_files = get_jpg_files(DOWNLOAD_DIR)
        new_files = current_files - notified

        for filename in new_files:
            data = filename.encode("utf-8")
            log.info("NOTIFY %s (%d bytes)", filename, len(data))
            char.setValue(data)
            notified.add(filename)

            # Small yield to let the notification propagate
            peripheral.waitForNotifications(0.05)

        # Prune notified set to avoid unbounded growth if files are deleted
        # over time. Keep notified set bounded to currently-existing files.
        notified = notified & current_files

if __name__ == "__main__":
    main()
