#!/usr/bin/env python3
"""
Sony a6400 Bluetooth file server.

Serves files from /home/dietpi/downloads/ over an RFCOMM socket.

Binary protocol (length-prefixed, minimal overhead):
  Command:
    [1 byte opcode] [2 bytes big-endian payload length] [payload]

  Response:
    [1 byte opcode] [2 bytes big-endian payload length] [payload]

Opcodes:
  0x01 LIST  — no payload. Response: 0x81 with newline-delimited filenames.
  0x02 GET   — payload is filename + quality byte. Response: 0x82 with JPEG bytes.
    Quality: 0=original, 1=half-size Q75, 2=1200px W Q75, 3=1200px W Q40

Error responses:
  0xFE — error, payload is ASCII error message.

Only one client at a time. Additional connections are rejected with 0xFE.
"""

import struct
import io
import bluetooth
import os
import logging

from PIL import Image

DOWNLOAD_DIR = "/home/dietpi/downloads"
RFCOMM_CHANNEL = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("a6400-bt")

# Opcodes
CMD_LIST = 0x01
CMD_GET  = 0x02
RSP_LIST = 0x81
RSP_GET  = 0x82
RSP_ERR  = 0xFE

MAX_PAYLOAD = 10 * 1024 * 1024  # 10 MB cap for GET payload read

def send_packet(sock, opcode, payload):
    """Send a length-prefixed packet: [opcode][len16][payload]."""
    header = struct.pack("!BH", opcode, len(payload))
    sock.sendall(header + payload)

def read_packet(sock):
    """Read a length-prefixed packet. Returns (opcode, payload_bytes)."""
    hdr = _recv_exact(sock, 3)
    if not hdr:
        return None, None
    opcode, plen = struct.unpack("!BH", hdr)
    payload = _recv_exact(sock, plen) if plen > 0 else b""
    if len(payload) != plen:
        raise ConnectionError("short read: expected %d got %d" % (plen, len(payload)))
    return opcode, payload

def _recv_exact(sock, n):
    """Read exactly n bytes, or return empty on EOF."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)
    return bytes(buf)

def handle_list():
    """Return newline-delimited list of .jpg and .jpeg files in DOWNLOAD_DIR."""
    try:
        names = sorted(
            f for f in os.listdir(DOWNLOAD_DIR)
            if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))
               and f.lower().endswith((".jpg", ".jpeg"))
        )
    except OSError as e:
        return RSP_ERR, str(e).encode()
    return RSP_LIST, ("\n".join(names) + "\n").encode()

def compress_jpeg(path, quality):
    """Read and optionally compress a JPEG. quality: 0=original, 1=half Q75, 2=1200w Q75, 3=1200w Q40."""
    if quality == 0:
        with open(path, "rb") as f:
            return f.read()
    img = Image.open(path)
    img.load()
    if quality == 1:
        resized = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
    target_w = 1200
    new_h = round(img.height * target_w / img.width)
    resized = img.resize((target_w, new_h), Image.LANCZOS)
    q = 75 if quality == 2 else 40
    buf = io.BytesIO()
    resized.save(buf, format="JPEG", quality=q)
    return buf.getvalue()

def handle_get(payload):
    """Read file from DOWNLOAD_DIR and return compressed JPEG bytes."""
    if len(payload) < 2:
        return RSP_ERR, b"EMPTY_GET_PAYLOAD"
    quality = payload[0]
    if quality > 3:
        return RSP_ERR, ("BAD_QUALITY: %d" % quality).encode()
    filename = payload[1:].decode("ascii", errors="replace")
    safe = os.path.basename(filename)
    path = os.path.join(DOWNLOAD_DIR, safe)
    if not os.path.isfile(path):
        return RSP_ERR, ("FILE_NOT_FOUND: %s" % safe).encode()
    try:
        data = compress_jpeg(path, quality)
        return RSP_GET, data
    except OSError as e:
        return RSP_ERR, ("READ_ERROR: %s" % e).encode()
    except Exception as e:
        return RSP_ERR, ("DECODE_ERROR: %s" % e).encode()

def handle_client(client_sock):
    """Process commands from a single client until disconnect."""
    log.info("client connected")
    try:
        while True:
            opcode, payload = read_packet(client_sock)
            if opcode is None:
                break  # disconnect

            if opcode == CMD_LIST:
                rsp_code, rsp_data = handle_list()
                log.info("LIST -> %d bytes", len(rsp_data))
            elif opcode == CMD_GET:
                if not payload:
                    send_packet(client_sock, RSP_ERR, b"EMPTY_GET_PAYLOAD")
                    continue
                quality = payload[0]
                filename = payload[1:].decode("ascii", errors="replace")
                rsp_code, rsp_data = handle_get(payload)
                log.info("GET %s q%d -> %d bytes (%02x)", filename, quality, len(rsp_data), rsp_code)
            else:
                log.warning("unknown opcode %02x", opcode)
                send_packet(client_sock, RSP_ERR, ("UNKNOWN_CMD: %02x" % opcode).encode())
                continue

            send_packet(client_sock, rsp_code, rsp_data)
    except ConnectionError as e:
        log.warning("client error: %s", e)
    except Exception as e:
        log.exception("unhandled error")
    finally:
        client_sock.close()
        log.info("client disconnected")

def main():
    log.info("starting Bluetooth file server on RFCOMM channel %d", RFCOMM_CHANNEL)

    srv = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    srv.bind(("", RFCOMM_CHANNEL))
    srv.listen(1)
    log.info("listening on RFCOMM channel %d — awaiting connection", RFCOMM_CHANNEL)

    while True:
        client_sock, addr = srv.accept()
        log.info("accepted from %s", addr)
        handle_client(client_sock)

if __name__ == "__main__":
    main()
