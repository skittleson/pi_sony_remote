# Sony a6400 Remote Capture

Tether your Sony a6400 to a Raspberry Pi and capture photos with a single press of the shutter — images are automatically downloaded, streamed over Bluetooth for mobile viewing, and served over HTTP for quick access.

Built for hands-free shooting scenarios: product photography, wildlife, events, or any situation where you want the camera on a tripod and the Pi handling everything else.

## How It Works

The system is composed of three independent services:

1. **Tethered Capture** — The Pi runs `gphoto2 --capture-tethered` in a persistent loop via a Lua wrapper. Press the camera shutter, and the photo is downloaded to `~/downloads/` with a sequential filename (`00001.jpg`, `00002.jpg`, ...). If the USB link drops, the service relaunches gphoto2 automatically.

2. **Bluetooth File Server** — A Python RFCOMM server exposes captured photos over Bluetooth with a custom binary protocol. Clients (like an Android phone) can list files and request them at different quality levels, with server-side JPEG compression to minimize transfer time over Bluetooth Classic.

3. **Copyparty File Server** — A lightweight HTTP file server serves the downloads directory with thumbnail generation and a grid view, making it easy to browse photos from any browser on the local network.

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

### Bluetooth Protocol

A length-prefixed binary protocol:

- **0x01 LIST** — Returns a newline-delimited list of JPEG filenames.
- **0x02 GET** — Payload is `<quality byte><filename>`. Quality levels:
  - `0` — Original (no compression)
  - `1` — Half-size, quality 75
  - `2` — 1200px wide, quality 75
  - `3` — 1200px wide, quality 40

Responses are `0x81` (LIST), `0x82` (GET data), or `0xFE` (error message).

## Prerequisites

- Raspberry Pi running DietPi/Raspbian (armhf or arm64)
- Sony a6400 with **Menu → Setup → USB Connection → PC Remote** enabled
- USB permissions: the service user must be in the `plugdev` group:
  ```bash
  sudo usermod -aG plugdev $USER
  ```
  Re-login for the group change to take effect.

## Installation

### Tethered Capture

```bash
bash setup.sh
```

This installs all system dependencies, builds gphoto2 2.5.32 from source (with SHA256 verification), configures USB permissions, and installs the systemd service.

After setup:

```bash
sudo systemctl enable --now a6400-capture
```

### Bluetooth File Server

```bash
sudo apt-get install -y python3-pip python3-bluez
pip3 install Pillow
python3 a6400_bt_server.py
```

### Copyparty File Server

```bash
bash copyparty-setup.sh
```

This installs copyparty and Pillow, then sets up a systemd service. After setup, access it at `http://<pi-ip>:8080` (login: `admin` / `admin`).

## Usage

### Capturing

Just press the camera shutter. Photos land in `~/downloads/` automatically.

```bash
tail -f ~/a6400_capture.log
```

### Service Management

```bash
sudo systemctl restart a6400-capture
sudo systemctl stop a6400-capture
journalctl -u a6400-capture -f
```

### Testing

```bash
python3 test_bt_server.py      # Fast unit tests (protocol, errors, path traversal)
python3 test_bt_compression.py  # Integration tests (JPEG quality, dimensions, sizes)
```

## File Reference

| File | Purpose |
|------|---------|
| `setup.sh` | Installs dependencies, builds gphoto2 2.5.32 from source, configures USB permissions |
| `a6400_capture.lua` | Tethered capture monitor — loops `gphoto2 --capture-tethered` with automatic restart |
| `a6400-capture.service` | systemd unit for the Lua capture monitor |
| `a6400_bt_server.py` | Bluetooth RFCOMM server with on-the-fly JPEG compression |
| `copyparty-setup.sh` | Installs and configures the copyparty HTTP file server |
| `copyparty-start.sh` | Startup wrapper for copyparty |
| `test_bt_server.py` | Unit tests for the Bluetooth server protocol |
| `test_bt_compression.py` | Integration tests for JPEG compression pipeline |

## Known Issues

- **USB mode switching:** The a6400 can fall back to charging mode (`054c:0994`) instead of PC Control (`054c:0caa`). A powered USB hub and a short, quality cable help. The service auto-recovers.
- **Camera must be on** and set to PC Remote mode.
- **Device contention:** If `gvfs-gphoto2-volume-monitor` holds the camera, captures fail with "Could not claim the USB device." Kill it with `pkill -f gvfs-gphoto2`. The service prevents this by maintaining a single persistent tethered session.
- **systemd WorkingDirectory gotcha:** gphoto2 writes a temporary capture file to the current working directory before moving it to the target. The default systemd CWD of `/` is not writable by the service user, so downloads silently fail. Fixed by `WorkingDirectory=/home/dietpi/downloads` in the unit file.

## Technical Notes

- gphoto2 is built from source (2.5.32) — the Raspbian repo only ships 2.5.28, and armhf has no other prebuilt option. The tarball SHA256 is verified during installation.
- The a6400 only exposes a **PC Control** profile to gphoto2 (no MTP variant), so `--list-files` and `file_added` events are unavailable. `--capture-tethered` is the only reliable shutter-triggered download method.
- Files are named with `%05n` (gphoto2's zero-padded counter). On restart, the monitor scans `~/downloads/` and continues from the highest existing number to prevent overwrites.
