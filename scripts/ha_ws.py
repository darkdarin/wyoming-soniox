"""Send one command to the Home Assistant WebSocket API and print the result as JSON.

Usage: HA_TOKEN=... python3 scripts/ha_ws.py TYPE ['{"key": "value"}']
Environment: HA_TOKEN (long-lived access token), HA_URL (default http://192.168.1.10:8123).

Standard library only (Python 3.9+), so it also runs with macOS's /usr/bin/python3, which macOS
keeps allowing on the local network when it blocks other interpreters.
"""

import base64
import json
import os
import socket
import struct
import sys
from urllib.parse import urlparse


def ws_connect(url: str) -> socket.socket:
    parsed = urlparse(url)
    sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(
        (
            f"GET /api/websocket HTTP/1.1\r\nHost: {parsed.netloc}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode()
    )
    # Byte by byte: the first WebSocket frame may follow the headers in the same packet.
    response = b""
    while not response.endswith(b"\r\n\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            sys.exit("Connection closed during the handshake")
        response += chunk
    status = response.split(b"\r\n", 1)[0].decode()
    if " 101 " not in status:
        sys.exit(f"Handshake failed: {status}")
    return sock


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            sys.exit("Connection closed")
        data += chunk
    return data


def ws_send(sock: socket.socket, message: dict) -> None:
    payload = json.dumps(message).encode()
    header = bytes([0x81])
    if len(payload) < 126:
        header += bytes([0x80 | len(payload)])
    elif len(payload) < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", len(payload))
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", len(payload))
    mask = os.urandom(4)
    sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def ws_recv(sock: socket.socket) -> dict:
    message = b""
    while True:
        first, second = recv_exact(sock, 2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", recv_exact(sock, 2))[0]
        elif size == 127:
            size = struct.unpack("!Q", recv_exact(sock, 8))[0]
        payload = recv_exact(sock, size)
        if first & 0x0F in (0x1, 0x0):  # text or continuation
            message += payload
            if first & 0x80:
                return json.loads(message)
        elif first & 0x0F == 0x8:
            sys.exit("Connection closed by Home Assistant")


def main() -> None:
    url = os.environ.get("HA_URL", "http://192.168.1.10:8123")
    command = {
        "id": 1,
        "type": sys.argv[1],
        **(json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}),
    }
    sock = ws_connect(url)
    ws_recv(sock)  # auth_required
    ws_send(sock, {"type": "auth", "access_token": os.environ["HA_TOKEN"]})
    auth = ws_recv(sock)
    if auth["type"] != "auth_ok":
        sys.exit(f"Auth failed: {auth.get('message')}")
    ws_send(sock, command)
    reply = ws_recv(sock)
    while reply.get("id") != 1:
        reply = ws_recv(sock)
    if not reply.get("success"):
        sys.exit(f"Error: {reply.get('error')}")
    print(json.dumps(reply["result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
