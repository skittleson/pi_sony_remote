#!/usr/bin/env python3
"""
Sony a6400 BLE notify server.

Monitors /home/dietpi/downloads/ for new JPEG files and sends a BLE
notification to any subscribed client with the filename (e.g. "00002.jpg").

Uses bluezero's peripheral/GATT server API. The bluezero GLib event loop
handles BLE events; a GLib timeout callback polls the filesystem at a
configurable interval.

Requires root (or bluetooth group) to access the BLE controller.
Requires bluezero (pip3 install bluezero).
"""

import logging
import os
import signal
import sys

from bluezero import adapter
from bluezero import async_tools
from bluezero import peripheral

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOWNLOAD_DIR = "/home/dietpi/downloads"
POLL_INTERVAL_SECONDS = 2

# Custom 128-bit UUIDs
SERVICE_UUID = "12341000-1234-1234-1234-123456789abc"
# 16-bit short UUID — BLE-compatible, no need for full 128-bit
CHAR_UUID = "2A6E"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("a6400-ble-notify")

# ---------------------------------------------------------------------------
# State — characteristic reference captured from the notify_callback
# ---------------------------------------------------------------------------

char_obj = None
notified = set()

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
# BLE callbacks
# ---------------------------------------------------------------------------

def on_notify_toggle(notifying, characteristic):
    """Called when a client enables or disables notifications.

    We capture the characteristic reference here so we can call
    set_value() from the poll callback.
    """
    global char_obj
    char_obj = characteristic
    if notifying:
        log.info("client subscribed to notifications")
    else:
        log.info("client unsubscribed from notifications")

def poll_files(_unused=None):
    """GLib timeout callback — poll for new JPEG files every interval.

    Returns True to keep the timeout active.
    """
    global notified

    current_files = get_jpg_files(DOWNLOAD_DIR)
    new_files = current_files - notified

    for filename in new_files:
        if char_obj:
            data = list(filename.encode("utf-8"))
            log.info("NOTIFY %s (%d bytes)", filename, len(data))
            char_obj.set_value(data)
        notified.add(filename)

    # Prune notified set — remove entries for files no longer on disk
    notified = notified & current_files

    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    adapter_address = list(adapter.Adapter.available())[0].address
    log.info("starting BLE notify server on %s (dir=%s, poll=%ds)",
             adapter_address, DOWNLOAD_DIR, POLL_INTERVAL_SECONDS)

    periph = peripheral.Peripheral(
        adapter_address,
        local_name="a6400-notify",
        appearance=1344,
    )

    periph.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)
    periph.add_characteristic(
        srv_id=1,
        chr_id=1,
        uuid=CHAR_UUID,
        value=[],
        notifying=False,
        flags=["notify"],
        read_callback=None,
        write_callback=None,
        notify_callback=on_notify_toggle,
    )

    # Graceful shutdown on SIGTERM / SIGINT — quit the GLib loop
    def _shutdown(signum, _frame):
        sig_name = signal.Signals(signum).name
        log.info("received %s — shutting down", sig_name)
        periph.mainloop.quit()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Register the filesystem poll timer (runs in GLib context)
    async_tools.add_timer_seconds(POLL_INTERVAL_SECONDS, poll_files)

    log.info("BLE advertising started (service=%s, char=%s)",
             SERVICE_UUID, CHAR_UUID)

    periph.publish()

if __name__ == "__main__":
    main()
