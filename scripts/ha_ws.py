"""Send one command to the Home Assistant WebSocket API and print the result as JSON.

Usage: uv run --env-file ../ha-yandex-station/main-ha.env scripts/ha_ws.py TYPE ['{"key": "value"}']
Environment: HA_TOKEN (long-lived access token), HA_URL (default http://192.168.1.10:8123).
"""

import asyncio
import json
import os
import sys

from websockets.asyncio.client import connect


async def main() -> None:
    url = os.environ.get("HA_URL", "http://192.168.1.10:8123").replace("http", "ws", 1)
    command = {
        "id": 1,
        "type": sys.argv[1],
        **(json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}),
    }
    async with connect(f"{url}/api/websocket", max_size=None) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        auth = json.loads(await ws.recv())
        if auth["type"] != "auth_ok":
            sys.exit(f"Auth failed: {auth.get('message')}")
        await ws.send(json.dumps(command))
        reply = json.loads(await ws.recv())
    if not reply.get("success"):
        sys.exit(f"Error: {reply.get('error')}")
    print(json.dumps(reply["result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
