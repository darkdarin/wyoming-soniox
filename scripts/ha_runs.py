"""Summarize recent Assist pipeline runs from pipeline_debug as TSV.

Usage: uv run --env-file ../ha-yandex-station/main-ha.env scripts/ha_runs.py PIPELINE_ID [SINCE_ISO]
Columns: start time, STT text, then seconds for stt-start->stt-end,
stt-vad-end->stt-end and stt-end->intent-end.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from websockets.asyncio.client import connect


async def main() -> None:
    pipeline_id = sys.argv[1]
    since = sys.argv[2] if len(sys.argv) > 2 else ""
    url = os.environ.get("HA_URL", "http://192.168.1.10:8123").replace("http", "ws", 1)
    async with connect(f"{url}/api/websocket", max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": os.environ["HA_TOKEN"]}))
        await ws.recv()
        await ws.send(
            json.dumps(
                {"id": 1, "type": "assist_pipeline/pipeline_debug/list", "pipeline_id": pipeline_id}
            )
        )
        runs = json.loads(await ws.recv())["result"]["pipeline_runs"]
        for n, run in enumerate(runs, start=2):
            if run["timestamp"] < since:
                continue
            await ws.send(
                json.dumps(
                    {
                        "id": n,
                        "type": "assist_pipeline/pipeline_debug/get",
                        "pipeline_id": pipeline_id,
                        "pipeline_run_id": run["pipeline_run_id"],
                    }
                )
            )
            events = json.loads(await ws.recv())["result"]["events"]
            times = {}
            text = ""
            for event in events:
                times.setdefault(event["type"], datetime.fromisoformat(event["timestamp"]))
                if event["type"] == "stt-end":
                    text = event["data"]["stt_output"]["text"]

            def span(a: str, b: str, times: dict = times) -> str:
                return (
                    f"{(times[b] - times[a]).total_seconds():.2f}"
                    if a in times and b in times
                    else "-"
                )

            print(
                "\t".join(
                    [
                        times["run-start"].astimezone().strftime("%H:%M:%S"),
                        text,
                        span("stt-start", "stt-end"),
                        span("stt-vad-end", "stt-end"),
                        span("stt-end", "intent-end"),
                    ]
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
