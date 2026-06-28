#!/usr/bin/env python3
"""Unit tests for a6400_ble_notify file monitoring logic.

The BLE peripheral cannot start without root and a BLE controller,
so these tests focus on the file monitoring and deduplication logic
that can be verified without hardware.
"""

import os
import sys
import tempfile

_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_here, '..', 'services'))

import a6400_ble_notify as bn

# ---------------------------------------------------------------------------
# File monitoring tests
# ---------------------------------------------------------------------------

def test_get_jpg_files():
    """get_jpg_files returns only jpg/jpeg files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for name in ("00001.jpg", "00002.jpeg", "readme.txt", ".hidden"):
            open(os.path.join(tmpdir, name), "w").close()
        result = bn.get_jpg_files(tmpdir)
        assert "00001.jpg" in result
        assert "00002.jpeg" in result
        assert "readme.txt" not in result
        assert ".hidden" not in result

def test_get_jpg_files_empty_dir():
    """Empty directory returns empty set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assert bn.get_jpg_files(tmpdir) == set()

def test_get_jpg_files_missing_dir():
    """Non-existent directory returns empty set (OSError handled)."""
    assert bn.get_jpg_files("/nonexistent/path") == set()

def test_deduplication():
    """Files already in the notified set are not detected as new."""
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "00001.jpg"), "w").close()
        notified = set()
        new = bn.get_jpg_files(tmpdir) - notified
        assert "00001.jpg" in new

        notified = {"00001.jpg"}
        new = bn.get_jpg_files(tmpdir) - notified
        assert "00001.jpg" not in new

        open(os.path.join(tmpdir, "00002.jpg"), "w").close()
        new = bn.get_jpg_files(tmpdir) - notified
        assert "00002.jpg" in new
        assert "00001.jpg" not in new

def test_prune_deleted():
    """Files deleted from disk are pruned from the notified set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "00001.jpg"), "w").close()
        notified = {"00001.jpg"}

        pruned = notified & bn.get_jpg_files(tmpdir)
        assert "00001.jpg" in pruned

        os.remove(os.path.join(tmpdir, "00001.jpg"))
        pruned = notified & bn.get_jpg_files(tmpdir)
        assert "00001.jpg" not in pruned

def test_poll_files_returns_true():
    """poll_files always returns True to keep the GLib timeout active."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Temporarily override the download dir for this test
        orig_dir = bn.DOWNLOAD_DIR
        bn.DOWNLOAD_DIR = tmpdir
        try:
            result = bn.poll_files(None)
            assert result is True
        finally:
            bn.DOWNLOAD_DIR = orig_dir

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_get_jpg_files,
        test_get_jpg_files_empty_dir,
        test_get_jpg_files_missing_dir,
        test_deduplication,
        test_prune_deleted,
        test_poll_files_returns_true,
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
