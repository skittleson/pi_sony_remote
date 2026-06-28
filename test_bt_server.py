#!/usr/bin/env python3
"""Fast unit tests for a6400_bt_server (no heavy compression)."""

import struct
import io
import sys
import threading

# Mock the bluetooth module if not available (local dev machine)
try:
    import bluetooth
except ImportError:
    import types
    bluetooth = types.ModuleType("bluetooth")
    bluetooth.RFCOMM = 1
    sys.modules["bluetooth"] = bluetooth

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

def test_get_jpg_files():
    """_get_jpg_files returns only jpg/jpeg files."""
    import os, tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in ("00001.jpg", "00002.jpeg", "readme.txt", ".hidden"):
            open(os.path.join(tmpdir, name), "w").close()
        orig_dir = bt.DOWNLOAD_DIR
        bt.DOWNLOAD_DIR = tmpdir
        try:
            result = bt._get_jpg_files()
            assert "00001.jpg" in result
            assert "00002.jpeg" in result
            assert "readme.txt" not in result
            assert ".hidden" not in result
        finally:
            bt.DOWNLOAD_DIR = orig_dir

def test_notify_dedup():
    """_wait_for_new_files deduplicates — same file not returned twice."""
    import os, tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "00001.jpg"), "w").close()
        orig_dir = bt.DOWNLOAD_DIR
        bt.DOWNLOAD_DIR = tmpdir
        try:
            notified = set()
            stop = threading.Event()
            f1 = bt._wait_for_new_files(notified, stop)
            assert f1 == "00001.jpg"
            notified.add(f1)
            # Same file should not be returned again
            notified.add(f1)
            # Simulate a new file
            open(os.path.join(tmpdir, "00002.jpg"), "w").close()
            f2 = bt._wait_for_new_files(notified, stop)
            assert f2 == "00002.jpg"
            # Stop event should cause immediate exit
            stop.set()
            f3 = bt._wait_for_new_files(notified, stop)
            assert f3 is None
        finally:
            bt.DOWNLOAD_DIR = orig_dir

def main():
    tests = [
        test_file_exists,
        test_original_passthrough,
        test_handle_list,
        test_handle_get_errors,
        test_path_traversal_blocked,
        test_packet_protocol,
        test_send_packet_format,
        test_get_jpg_files,
        test_notify_dedup,
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
