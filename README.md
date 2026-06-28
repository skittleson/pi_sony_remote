<div align="center">

# Sony a6400 Remote Capture

**Tether your Sony a6400 to a Raspberry Pi — capture, download, and serve photos hands-free.**
No laptop. No phone. Press the shutter and walk away.

![Python 3](https://img.shields.io/badge/Python-3-blue?style=flat-square)
![gphoto2 2.5.32](https://img.shields.io/badge/gphoto2-2.5.32-green?style=flat-square)
![systemd](https://img.shields.io/badge/systemd-service-orange?style=flat-square)
![Bluetooth RFCOMM](https://img.shields.io/badge/Bluetooth-RFCOMM-blueviolet?style=flat-square)
![BLE Notify](https://img.shields.io/badge/BLE-Notify-cyan?style=flat-square)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen?style=flat-square)](LICENSE)

[Quick start](#quick-start) · [Features](#features) · [BLE notify](#ble-notify) · [Architecture](#architecture) · [Configuration](#configuration) · [Troubleshooting](#troubleshooting)

</div>

---

Most tethered shooting setups need a laptop open and connected, or a phone
running a camera app. This puts **everything on a Raspberry Pi** — capture,
download, Bluetooth transfer, and HTTP browsing. The camera is on a tripod.
The Pi is on a shelf. You press the shutter, and the photo appears on your
phone over Bluetooth or your browser over LAN. No laptop required.

## Why I built this

I needed a way to shoot product photos and wildlife without sitting at a
computer. The a6400 supports PC Remote mode over USB, and gphoto2 can
handle the tethered capture, but getting the photos from the Pi to a
viewing device in the field means something more than an FTP server on a
phone. Bluetooth works everywhere. HTTP works everywhere. Both together
covers every scenario.

That goal forced a few hard choices. Build gphoto2 from source because
Raspbian only ships 2.5.28 and the a6400 needs the latest. Name files
with a counter because gphoto2's default timestamps produce filenames that
sort wrong on mobile. Compress JPEGs server-side because Bluetooth
Classic is slow enough already.

Built for product photography, wildlife, events, and any situation where
the camera is on a tripod and the photographer shouldn't need to be at a
computer.

## Quick start

```bash
git clone https://github.com/skittleson/pi_sony_remote.git
cd pi_sony_remote

# One command installs everything: gphoto2 from source, USB permissions, systemd service
bash setup.sh

# Start the capture service
sudo systemctl enable --now a6400-capture
```

Then press the camera shutter. Photos land in `~/downloads/` automatically.

```bash
# Watch captures in real time
tail -f ~/a6400_capture.log

# Browse photos from any browser on the LAN
bash copyparty-setup.sh && sudo systemctl enable --now copyparty
# → http://<pi-ip>:8080  (login: admin / admin)
```

Transfer to a phone over Bluetooth:

```bash
sudo apt-get install -y python3-pip python3-bluez
pip3 install Pillow
python3 a6400_bt_server.py
# → Android client connects and can list/download with quality-level compression
```

BLE notify (instant photo alerts over Bluetooth Low Energy):

```bash
sudo systemctl enable --now a6400-ble-notify
# → Pi advertises over BLE; Android client gets notified on each new capture
```

## Pairing from a Linux laptop

To pair the Pi with a Linux laptop so you can test the Bluetooth server
from the command line:

### 1. On the Pi — make it discoverable and pairable

```bash
ssh dietpi@<pi-ip>
echo -e 'discoverable on\npairable on\nexit' | bluetoothctl
```

Then register a D-Bus agent so the Pi accepts pairing without prompting:

```bash
python3 -c "
import dbus
bus = dbus.SystemBus()
agent_mgr = dbus.Interface(bus.get_object('org.bluez', '/org/bluez'),
                           'org.bluez.AgentManager1')
agent_mgr.RegisterAgent('/test/agent', 'NoInputNoOutput')
agent_mgr.RequestDefaultAgent('/test/agent')
print('Agent registered — Pi will accept pairing requests')
import time; time.sleep(90)
"
```

Leave this running in the foreground for at least 90 seconds (or longer
if you need more time).

### 2. On the laptop — find the Pi's address

If you don't know the Pi's BD address, scan from the laptop:

```bash
bluetoothctl <<EOF
scan on
EOF
```

Look for the device named "DietPi" (or whatever the Pi's hostname is).
Note its MAC address (e.g. `B8:27:EB:E5:8F:0C`).

Alternatively, read it from the Pi directly:

```bash
ssh dietpi@<pi-ip> "python3 -c \"
import dbus
bus = dbus.SystemBus()
props = dbus.Interface(bus.get_object('org.bluez', '/org/bluez/hci0'),
                       'org.freedesktop.DBus.Properties')
print(props.Get('org.bluez.Adapter1', 'Address'))
\""
```

### 3. On the laptop — pair and trust

```bash
bluetoothctl <<EOF
trust B8:27:EB:E5:8F:0C
connect B8:27:EB:E5:8F:0C
exit
EOF
```

The `trust` is required — without it, RFCOMM socket connections are
denied by the kernel.

### 4. Test the connection

After pairing, you can test the RFCOMM server from the laptop:

```python
import socket, struct

AF_BLUETOOTH = 31
SOCK_STREAM = 1
BTPROTO_RFCOMM = 3

sock = socket.socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)
sock.settimeout(30)
sock.connect(('B8:27:EB:E5:8F:0C', 3))

# LIST request
sock.send(struct.pack("!BI", 0x01, 0))
hdr = sock.recv(5)
opcode, length = struct.unpack("!BI", hdr)
filenames = sock.recv(length)
print(filenames.decode())

sock.close()
```

### Troubleshooting

- **"Device not available"** — the Pi isn't in range or discoverable mode
  expired. Run `discoverable on` again on the Pi.
- **"Authentication Rejected"** — no D-Bus agent is running on the Pi.
  See step 1 above.
- **"Connection refused"** — the `a6400-bluetooth.service` isn't running.
  Start it: `sudo systemctl start a6400-bluetooth`
- **"Permission denied"** — the device isn't trusted. Run `trust <mac>`
  in `bluetoothctl`.

## Features

- **Tethered capture** — `gphoto2 --capture-tethered` in a persistent Lua loop with automatic restart on USB drop
- **Sequential filenames** — `00001.jpg`, `00002.jpg`, ... (gphoto2's `%05n` counter, with restart-safe scan to prevent overwrites)
- **Bluetooth RFCOMM server** — custom binary protocol with server-side JPEG compression at 4 quality levels
- **Bluetooth quality tiers** — original (0), half-size quality 75 (1), 1200px wide quality 75 (2), 1200px wide quality 40 (3)
- **Copyparty HTTP server** — thumbnails, grid view, browse from any LAN browser at `http://<pi-ip>:8080`
- **USB auto-recovery** — Lua monitor detects gphoto2 failures from USB drops and relaunches the tethered session
- **systemd integration** — capture runs as a persistent service with journal logging
- **BLE notify** — instant Bluetooth Low Energy notification on each new capture; Android client wakes and connects via RFCOMM
- **Source-verified gphoto2** — built from source (2.5.32) with SHA256 verification; Raspbian only ships 2.5.28

<details>
<summary>Use cases</summary>

- **Product photography** — camera on tripod, Pi on shelf, trigger shutter and check phone over Bluetooth
- **Wildlife** — remote trigger with instant photo availability on mobile
- **Events** — hands-free capture station where attendees can review photos on LAN
- **Booths and displays** — self-contained photo station with no laptop footprint

</details>

## BLE notify

The BLE notify service runs alongside the existing RFCOMM server as a
separate `systemd` unit. It monitors `/home/dietpi/downloads/` for new
JPEG files and sends a Bluetooth Low Energy notification to any connected
Android client.

When the Android client receives the notification, it wakes up and connects
to the RFCOMM server to fetch the file using the existing binary protocol.

### How it works

1. The BLE server polls `/home/dietpi/downloads/` every 2 seconds for
   new `.jpg` files
2. On first detection of each file, it sends the filename (e.g. `00002.jpg`)
   as a BLE notification to all subscribed clients
3. Duplicates are suppressed — the same file never triggers more than one
   notification
4. The Pi advertises with a custom service UUID so clients can discover it

### Custom UUIDs

| Item | UUID |
|------|------|
| Service | `12341000-1234-1234-1234-123456789abc` |
| Characteristic | `2A6E` (BLE short UUID) |

The characteristic value is the filename as UTF-8 bytes. Filenames are
max 12 bytes (`NNNNN.jpg`), well within the BLE ATT MTU of 20 bytes.

### systemd management

```bash
# Start the BLE notify service
sudo systemctl enable --now a6400-ble-notify

# Check status
sudo systemctl status a6400-ble-notify

# View logs
journalctl -u a6400-ble-notify -f

# Stop
sudo systemctl stop a6400-ble-notify
```

### Testing from a Linux laptop

Run the included end-to-end test script:

```bash
sudo python3 e2e_ble_notify_test.py <PI_MAC_ADDRESS>
```

The script connects, enables notifications, and listens for 60 seconds.
Create a new `.jpg` file in `/home/dietpi/downloads/` on the Pi to trigger
a notification.

### Notes

- Requires root (or `bluetooth` group) to access the BLE controller
- Notifications are fire-and-forget — if no client is connected at the
  time of capture, the notification is lost (no queuing)
- The BLE service and RFCOMM server run as separate `systemd` units for
  process isolation

## Architecture

```
Sony a6400 (PC Remote mode)
        │
        │ USB
        ▼
   gphoto2 --capture-tethered
        │
        ▼
   ~/downloads/NNNNN.jpg
        │
        ├──► BLE notify                ──► Android client (wakes on new capture)
        ├──► Bluetooth RFCOMM server   ──► Android / mobile client
        └──► Copyparty HTTP server     ──► Browser on LAN
```

### Bluetooth protocol

A length-prefixed binary protocol:

- **0x01 LIST** — returns a newline-delimited list of JPEG filenames
- **0x02 GET** — payload is `<quality byte><filename>`; quality levels:
  - `0` — original (no compression)
  - `1` — half-size, quality 75
  - `2` — 1200px wide, quality 75
  - `3` — 1200px wide, quality 40

Responses are `0x81` (LIST result), `0x82` (GET data), or `0xFE` (error message).

## Configuration

All three services can run simultaneously, or independently:

| Service | Command | Port/Protocol | Notes |
|---------|---------|---------------|-------|
| Tethered capture | `sudo systemctl enable --now a6400-capture` | USB | Auto-restarts on USB drop |
| BLE notify | `sudo systemctl enable --now a6400-ble-notify` | BLE (GATT) | Requires bluezero (pip3 install bluezero) |
| Bluetooth server | `python3 a6400_bt_server.py` | RFCOMM | Requires Pillow, bluez |
| HTTP server | `bash copyparty-setup.sh && sudo systemctl enable --now copyparty` | `:8080` | Login: admin/admin |

## Hardware

| Component | Requirement |
|-----------|-------------|
| Camera | Sony a6400 with **Menu → Setup → USB Connection → PC Remote** |
| Pi | Raspberry Pi (armhf or arm64) running DietPi/Raspbian |
| USB cable | Short, quality cable; powered hub helps with USB mode stability |

## Troubleshooting

- **USB mode switching** — The a6400 can fall back to charging mode (`054c:0994`) instead of PC Control (`054c:0caa`). Use a powered USB hub and a short, quality cable. The service auto-recovers.
- **Camera must be on** and set to PC Remote mode before connecting USB.
- **Device contention** — If `gvfs-gphoto2-volume-monitor` holds the camera, captures fail with "Could not claim the USB device." Fix: `pkill -f gvfs-gphoto2`. The service prevents this by maintaining a single persistent tethered session.
- **systemd WorkingDirectory** — gphoto2 writes a temporary capture file to the current working directory before moving it to the target. The default systemd CWD of `/` is not writable by the service user, causing silent download failures. Fixed by `WorkingDirectory=/home/dietpi/downloads` in the unit file.

## Testing

```bash
python3 test_bt_server.py          # Unit tests (protocol, errors, path traversal)
python3 test_bt_compression.py     # Integration tests (JPEG quality, dimensions, sizes)
python3 test_ble_notify.py        # Unit tests (file monitoring, deduplication)
sudo python3 e2e_ble_notify_test.py <mac>  # End-to-end BLE notify test
```

## File Reference

| File | Purpose |
|------|---------|
| `setup.sh` | Installs dependencies, builds gphoto2 2.5.32 from source with SHA256 verification, configures USB permissions |
| `a6400_capture.lua` | Tethered capture monitor — loops `gphoto2 --capture-tethered` with automatic restart |
| `a6400-capture.service` | systemd unit for the Lua capture monitor |
| `a6400_ble_notify.py` | BLE GATT server — monitors for new captures and sends filename notifications |
| `a6400-ble-notify.service` | systemd unit for the BLE notify server |
| `a6400_bt_server.py` | Bluetooth RFCOMM server with on-the-fly JPEG compression |
| `copyparty-setup.sh` | Installs and configures the copyparty HTTP file server |
| `copyparty-start.sh` | Startup wrapper for copyparty |
| `test_bt_server.py` | Unit tests for the Bluetooth server protocol |
| `test_bt_compression.py` | Integration tests for JPEG compression pipeline |
| `test_ble_notify.py` | Unit tests for BLE notify file monitoring and deduplication |
| `e2e_ble_notify_test.py` | End-to-end test client for BLE notifications |
