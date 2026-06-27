<div align="center">

# Sony a6400 Remote Capture

**Tether your Sony a6400 to a Raspberry Pi — capture, download, and serve photos hands-free.**
No laptop. No phone. Press the shutter and walk away.

![Python 3](https://img.shields.io/badge/Python-3-blue?style=flat-square)
![gphoto2 2.5.32](https://img.shields.io/badge/gphoto2-2.5.32-green?style=flat-square)
![systemd](https://img.shields.io/badge/systemd-service-orange?style=flat-square)
![Bluetooth RFCOMM](https://img.shields.io/badge/Bluetooth-RFCOMM-blueviolet?style=flat-square)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen?style=flat-square)](LICENSE)

[Quick start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [Configuration](#configuration) · [Troubleshooting](#troubleshooting)

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

## Features

- **Tethered capture** — `gphoto2 --capture-tethered` in a persistent Lua loop with automatic restart on USB drop
- **Sequential filenames** — `00001.jpg`, `00002.jpg`, ... (gphoto2's `%05n` counter, with restart-safe scan to prevent overwrites)
- **Bluetooth RFCOMM server** — custom binary protocol with server-side JPEG compression at 4 quality levels
- **Bluetooth quality tiers** — original (0), half-size quality 75 (1), 1200px wide quality 75 (2), 1200px wide quality 40 (3)
- **Copyparty HTTP server** — thumbnails, grid view, browse from any LAN browser at `http://<pi-ip>:8080`
- **USB auto-recovery** — Lua monitor detects gphoto2 failures from USB drops and relaunches the tethered session
- **systemd integration** — capture runs as a persistent service with journal logging
- **Source-verified gphoto2** — built from source (2.5.32) with SHA256 verification; Raspbian only ships 2.5.28

<details>
<summary>Use cases</summary>

- **Product photography** — camera on tripod, Pi on shelf, trigger shutter and check phone over Bluetooth
- **Wildlife** — remote trigger with instant photo availability on mobile
- **Events** — hands-free capture station where attendees can review photos on LAN
- **Booths and displays** — self-contained photo station with no laptop footprint

</details>

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
        ├──► Bluetooth RFCOMM server  ──► Android / mobile client
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
```

## File Reference

| File | Purpose |
|------|---------|
| `setup.sh` | Installs dependencies, builds gphoto2 2.5.32 from source with SHA256 verification, configures USB permissions |
| `a6400_capture.lua` | Tethered capture monitor — loops `gphoto2 --capture-tethered` with automatic restart |
| `a6400-capture.service` | systemd unit for the Lua capture monitor |
| `a6400_bt_server.py` | Bluetooth RFCOMM server with on-the-fly JPEG compression |
| `copyparty-setup.sh` | Installs and configures the copyparty HTTP file server |
| `copyparty-start.sh` | Startup wrapper for copyparty |
| `test_bt_server.py` | Unit tests for the Bluetooth server protocol |
| `test_bt_compression.py` | Integration tests for JPEG compression pipeline |
