#!/usr/bin/env python3
"""End-to-end test for a6400_bt_server RFCOMM protocol.

Usage:
  On the Pi (server):
    python3 a6400_bt_server.py

  On a Linux laptop (client):
    python3 e2e_bt_server_test.py <BDADDR>
    e.g. python3 e2e_bt_server_test.py B8:27:EB:E5:8F:0C

Requires:
  pip install pybluez
"""

import socket
import struct
import sys
import time

import bluetooth

PORT = 1
CHUNK = 4096

def send_packet(sock, opcode, payload=b""):
    sock.send(struct.pack("!BI", opcode, len(payload)) + payload)

def read_packet(sock):
    header = b""
    while len(header) < 5:
        chunk = sock.recv(5 - len(header))
        if not chunk:
            return None, None
        header += chunk
    opcode, length = struct.unpack("!BI", header)
    data = b""
    while len(data) < length:
        chunk = sock.recv(min(length - len(data), CHUNK))
        if not chunk:
            return opcode, data
        data += chunk
    return opcode, data

def test_list(bdaddr):
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((bdaddr, PORT))
    send_packet(sock, 0x01)
    opcode, payload = read_packet(sock)
    assert opcode == 0x81, f"Expected 0x81, got 0x{opcode:02x}"
    names = payload.decode().strip().split("\n")
    assert len(names) > 0, "LIST returned no files"
    for n in names:
        assert n.lower().endswith((".jpg", ".jpeg")), f"Bad name: {n}"
    sock.close()
    print(f"[PASS] LIST returned {len(names)} files")

def test_get(bdaddr):
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((bdaddr, PORT))
    send_packet(sock, 0x01)
    opcode, payload = read_packet(sock)
    names = payload.decode().strip().split("\n")
    name = names[0]

    # Test quality 0 (original)
    send_packet(sock, 0x02, bytes([0]) + name.encode())
    opcode, payload = read_packet(sock)
    assert opcode == 0x82, f"GET q0: Expected 0x82, got 0x{opcode:02x}"
    assert len(payload) > 100, f"GET q0: payload too small ({len(payload)} bytes)"
    sock.close()
    print(f"[PASS] GET q0: {len(payload)} bytes for {name}")

    # Test quality 1 (compressed)
    sock2 = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock2.connect((bdaddr, PORT))
    send_packet(sock2, 0x02, bytes([1]) + name.encode())
    opcode, payload = read_packet(sock2)
    assert opcode == 0x82, f"GET q1: Expected 0x82, got 0x{opcode:02x}"
    sock2.close()
    print(f"[PASS] GET q1: {len(payload)} bytes for {name}")

def test_wait_notify(bdaddr):
    """Test WAIT/NOTIFY: send CMD_WAIT, create a new file, expect RSP_NOTIFY."""
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((bdaddr, PORT))

    # Enter wait mode
    send_packet(sock, 0x03)
    opcode, payload = read_packet(sock)
    assert opcode == 0x81, f"WAIT ack: Expected 0x81, got 0x{opcode:02x}"

    # Create a trigger file on the Pi
    import subprocess
    subprocess.run(
        ["ssh", "dietpi@192.168.22.145",
         f"touch /home/dietpi/downloads/trigger_{int(time.time())}.jpg"],
        check=False,
    )

    # Wait up to 10 seconds for NOTIFY
    sock.settimeout(10)
    try:
        opcode, payload = read_packet(sock)
        assert opcode == 0x83, f"NOTIFY: Expected 0x83, got 0x{opcode:02x}"
        filename = payload.decode()
        print(f"[PASS] WAIT/NOTIFY received: {filename}")
    except socket.timeout:
        print("[FAIL] WAIT/NOTIFY: no NOTIFY received within 10s")

    sock.close()

def test_error_handling(bdaddr):
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((bdaddr, PORT))

    # Bad quality
    send_packet(sock, 0x02, bytes([9]) + b"test.jpg")
    opcode, payload = read_packet(sock)
    assert opcode == 0xFE, f"Bad quality error: Expected 0xFE, got 0x{opcode:02x}"
    sock.close()
    print(f"[PASS] Error handling: {payload.decode()}")

def main():
    bdaddr = sys.argv[1] if len(sys.argv) > 1 else "B8:27:EB:E5:8F:0C"
    print(f"Connecting to {bdaddr}...")

    test_list(bdaddr)
    test_get(bdaddr)
    test_error_handling(bdaddr)
    # test_wait_notify requires creating a file on the Pi — skip by default
    # test_wait_notify(bdaddr)

    print("\nAll tests passed.")

if __name__ == "__main__":
    main()
