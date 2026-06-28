#!/usr/bin/env python3
"""Integration test: compression produces valid, decodable JPEGs with correct dimensions.

Run on the Pi: timeout 120 python3 test_bt_compression.py
"""

import os
import struct
import io
import sys

_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_here, '..', 'services'))

from PIL import Image
import a6400_bt_server as bt

TEST_FILE = "/home/dietpi/downloads/00001.jpg"

# Expected dimensions per quality level
EXPECTED = {
    0: None,  # original, don't check dimensions (slow to reopen)
    1: (3000, 1688),  # half of 6000x3376
    2: (1200, 675),    # 1200px wide
    3: (1200, 675),    # 1200px wide
}

def test_compression_decodable():
    """Each compressed output must be a valid, decodable JPEG with correct dimensions."""
    orig = Image.open(TEST_FILE)
    orig.load()
    orig_w, orig_h = orig.size

    for q in range(1, 4):
        data = bt.compress_jpeg(TEST_FILE, q)

        # Must start with JPEG magic
        assert data[:2] == b"\xff\xd8", f"q={q}: not JPEG (magic={data[:2].hex()})"

        # Must be decodable
        img = Image.open(io.BytesIO(data))
        img.load()

        # Check dimensions
        if q in EXPECTED:
            expected_w, expected_h = EXPECTED[q]
            actual_w, actual_h = img.size
            assert actual_w == expected_w and actual_h == expected_h, \
                f"q={q}: expected {expected_w}x{expected_h}, got {actual_w}x{actual_h}"

        # Must be RGB (Android can decode)
        assert img.mode == "RGB", f"q={q}: mode={img.mode}, expected RGB"

        print(f"  q={q}: {img.size[0]}x{img.size[1]}, {len(data)} bytes, mode={img.mode} OK")

def test_compression_size_bounds():
    """Compressed output must be significantly smaller than original."""
    import os
    orig_size = os.path.getsize(TEST_FILE)

    # q=0: exact original
    data0 = bt.compress_jpeg(TEST_FILE, 0)
    assert len(data0) == orig_size, f"q=0: {len(data0)} != {orig_size}"

    # q=1: <5% of original
    data1 = bt.compress_jpeg(TEST_FILE, 1)
    assert len(data1) < orig_size * 0.05, f"q=1 too large: {len(data1)}"

    # q=2: <1% of original
    data2 = bt.compress_jpeg(TEST_FILE, 2)
    assert len(data2) < orig_size * 0.01, f"q=2 too large: {len(data2)}"

    # Monotonic decreasing
    data3 = bt.compress_jpeg(TEST_FILE, 3)
    assert len(data1) > len(data2) > len(data3), "sizes not monotonic"

    print(f"  sizes monotonic: q1={len(data1)}, q2={len(data2)}, q3={len(data3)} OK")

def test_get_with_compression():
    """handle_get with quality byte returns valid decodable JPEG."""
    for q in range(1, 4):
        payload = bytes([q]) + b"00001.jpg"
        code, data = bt.handle_get(payload)
        assert code == bt.RSP_GET, f"q={q}: expected RSP_GET, got {code:#x}"

        # Must be decodable
        img = Image.open(io.BytesIO(data))
        img.load()
        assert img.mode == "RGB", f"q={q}: mode={img.mode}"

        print(f"  q={q}: GET returned {len(data)} bytes, decodable OK")

def main():
    tests = [
        test_compression_decodable,
        test_compression_size_bounds,
        test_get_with_compression,
    ]
    passed = failed = 0
    for t in tests:
        try:
            print(f"[RUN] {t.__name__}:")
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
