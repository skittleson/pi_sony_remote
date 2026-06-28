#!/bin/bash
set -e

echo "=== a6400 Remote Capture Setup ==="

# Install system dependencies
echo "[1/4] Installing system packages..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    build-essential libgphoto2-dev libjpeg-dev libexif-dev \
    libpopt-dev libcdk5-dev libreadline-dev bzip2 pkg-config \
    lua5.4

# Build gphoto2 2.5.32 from source
echo "[2/4] Building gphoto2 2.5.32 from source..."
cd /tmp
curl -sL "https://github.com/gphoto/gphoto2/releases/download/v2.5.32/gphoto2-2.5.32.tar.bz2" \
    -o gphoto2-2.5.32.tar.bz2

EXPECTED_SHA="4e379a0f12f72b49ee5ee2283ffd806b5d12d099939d75197a3f4bbc7f27a1a1"
ACTUAL_SHA=$(sha256sum gphoto2-2.5.32.tar.bz2 | cut -d' ' -f1)

if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "ERROR: SHA256 mismatch! Expected $EXPECTED_SHA, got $ACTUAL_SHA"
    exit 1
fi
echo "  SHA256 verified."

tar xjf gphoto2-2.5.32.tar.bz2
cd gphoto2-2.5.32
./configure --prefix=/usr/local --quiet
make -j$(nproc)
sudo make install
sudo ldconfig
hash -r

GPHOTO_VER=$(/usr/local/bin/gphoto2 --version 2>/dev/null | head -1)
echo "  Installed: $GPHOTO_VER"

# Set up USB permissions
echo "[3/4] Configuring USB permissions..."
sudo usermod -aG plugdev "$USER"

# Install the capture monitor and systemd service
echo "[4/4] Installing capture monitor and service..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/../services/sony_camera_capture.lua" "$HOME/sony_camera_capture.lua"

chmod +x "$HOME/sony_camera_capture.lua"
if [ -f "$SCRIPT_DIR/systemd/sony_camera-capture.service" ]; then
    sudo cp "$SCRIPT_DIR/systemd/sony_camera-capture.service" /etc/systemd/system/sony_camera-capture.service

    sudo systemctl enable sony_camera-capture
    echo "  Service installed and enabled."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Start the service now (after re-login for plugdev group):"
echo "  sudo systemctl start sony_camera-capture"
echo ""
echo "Then just press the camera shutter — photos land in ~/downloads/"
echo "Watch activity:  tail -f ~/sony_camera_capture.log"
echo ""
echo "NOTE: Re-login for plugdev group changes to take effect before starting."
