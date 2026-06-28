#!/usr/bin/env python3
"""Fast unit tests for a6400_bt_server (no heavy compression)."""

import struct
import io
import sys

import a6400_bt_server as bt

def test_file_exists():
    import os
    assert os.path.isfile("/home/dietpi/downloads/00001.jpg")

def test_original_passthrough():
    """q=0 returns exact file bytes."""
    import os
    with open("/home/dietpi/downloads/00001.jpg", "rb") as f:
        orig = f.read()
    data = bt.compress_jpeg("/home/dietpi/downloads/00001.jpg", 0)
    assert data == orig

def test_handle_list():
    code, data = bt.handle_list()
    assert code == bt.RSP_LIST
    assert b"00001.jpg" in data
    for name in data.decode().strip().split("\n"):
        assert name.lower().endswith((".jpg", ".jpeg"))

def test_handle_get_errors():
    # Short payload
    code, _ = bt.handle_get(b"00001.jpg")
    assert code == bt.RSP_ERR

    # Bad quality
    code, _ = bt.handle_get(bytes([5]) + b"00001.jpg")
    assert code == bt.RSP_ERR

    # File not found
    code, data = bt.handle_get(bytes([0]) + b"zzz.jpg")
    assert code == bt.RSP_ERR
    assert b"FILE_NOT_FOUND" in data

def test_path_traversal_blocked():
    code, data = bt.handle_get(bytes([0]) + b"../etc/passwd")
    assert code == bt.RSP_ERR
    assert b"FILE_NOT_FOUND" in data

def test_packet_protocol():
    """Verify read_packet and send_packet roundtrip correctly over socketpair."""
    import socket as stdsocket
    rsock, wsock = stdsocket.socketpair()

    # Send a packet with payload
    bt.send_packet(wsock, 0xAB, b"test payload")
    op, data = bt.read_packet(rsock)
    assert op == 0xAB
    assert data == b"test payload"

    # Send empty payload packet
    bt.send_packet(wsock, bt.CMD_LIST, b"")
    op, data = bt.read_packet(rsock)
    assert op == bt.CMD_LIST
    assert data == b""

    # Send binary payload
    bt.send_packet(wsock, bt.CMD_GET, bytes([1]) + b"00001.jpg")
    op, data = bt.read_packet(rsock)
    assert op == bt.CMD_GET
    assert data == bytes([1]) + b"00001.jpg"

    rsock.close()
    wsock.close()

def test_send_packet_format():
    """send_packet produces correct wire format."""
    import socket as stdsocket
    rsock, wsock = stdsocket.socketpair()
    bt.send_packet(wsock, 0xAB, b"hello")
    raw = rsock.recv(1000)
    assert raw[0] == 0xAB
    assert struct.unpack("!I", raw[1:5])[0] == 5
    assert raw[5:] == b"hello"
    rsock.close()
    wsock.close()

def main():
    tests = [
        test_file_exists,
        test_original_passthrough,
        test_handle_list,
        test_handle_get_errors,
        test_path_traversal_blocked,
        test_packet_protocol,
        test_send_packet_format,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
