#!/bin/bash
# Copyparty setup script for Raspberry Pi (DietPi)
# Serves /home/dietpi/downloads with thumbnail support
set -e

echo "=== Copyparty Setup ==="

# Install Python and dependencies
echo "[1/4] Installing system packages..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-pip zlib1g-dev libjpeg62-turbo-dev python3-dev

# Install copyparty and Pillow
echo "[2/4] Installing copyparty and Pillow..."
pip3 install --break-system-packages copyparty Pillow

# Create startup script
echo "[3/4] Creating startup script..."
cat > /home/dietpi/copyparty-start.sh << 'INNER'
#!/bin/bash
exec /home/dietpi/.local/bin/copyparty \
  -a admin:admin \
  -v '/home/dietpi/downloads::r:A,admin' \
  -i 0.0.0.0 -p 8080 \
  --grid
INNER
chmod +x /home/dietpi/copyparty-start.sh

# Create systemd service
echo "[4/4] Creating systemd service..."
sudo tee /etc/systemd/system/copyparty.service > /dev/null << 'EOF'
[Unit]
Description=CopyParty File Server (Photos)
After=network.target

[Service]
Type=simple
User=dietpi
Environment=LC_ALL=C.UTF-8
ExecStart=/home/dietpi/copyparty-start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable copyparty
sudo systemctl start copyparty

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Access copyparty at: http://<your-pi-ip>:8080"
echo "Login: admin / admin"
echo "Change the password in /home/dietpi/copyparty-start.sh"
echo ""
echo "Service status: sudo systemctl status copyparty"
