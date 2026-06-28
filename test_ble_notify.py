#!/usr/bin/env python3
"""Unit tests for a6400_ble_notify (file monitoring and GATT structure).

The actual BLE peripheral cannot start without root and a BLE controller,
so these tests focus on the logic that can be verified locally:

  - File polling and deduplication
  - GATT service has correct UUID and properties (hardware-dependent)
  - Notify characteristic sends correct filename bytes (hardware-dependent)
"""

import os
import sys
import tempfile

import a6400_ble_notify as bn

# ---------------------------------------------------------------------------
# GATT structure tests (skip if bluepy lacks peripheral API)
# ---------------------------------------------------------------------------

class SkipTest(Exception):
    """Raised when a test should be skipped (e.g. no BLE hardware)."""

def _skip_if_no_peripheral_api():
    """Skip tests requiring bluepy peripheral mode."""
    import bluepy.btle as btle
    if not hasattr(btle, 'CHAR_PROP_NOTIFY'):
        raise SkipTest("bluepy lacks CHAR_PROP_NOTIFY (peripheral mode not available)")

def test_service_uuid():
    _skip_if_no_peripheral_api()
    svc = bn.NotifyService()
    assert str(svc.uuid) == bn.SERVICE_UUID

def test_char_uuid_and_properties():
    _skip_if_no_peripheral_api()
    char = bn.NotifyCharacteristic()
    assert str(char.uuid) == bn.CHAR_UUID
    import bluepy.btle as btle
    assert char.properties == btle.CHAR_PROP_NOTIFY

def test_notify_value():
    _skip_if_no_peripheral_api()
    char = bn.NotifyCharacteristic()
    char.setValue(b"00002.jpg")
    assert char.getValue() == b"00002.jpg"

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

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_service_uuid,
        test_char_uuid_and_properties,
        test_notify_value,
        test_get_jpg_files,
        test_get_jpg_files_empty_dir,
        test_get_jpg_files_missing_dir,
        test_deduplication,
        test_prune_deleted,
    ]
    passed = failed = skipped = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
            passed += 1
        except SkipTest as e:
            print(f"[SKIP] {t.__name__}: {e}")
            skipped += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
