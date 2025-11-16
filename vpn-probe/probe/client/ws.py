import asyncio
import json
from typing import AsyncGenerator, Callable, Dict

import websockets


class ProbeClient:
    def __init__(self, url: str, api_key: str, server_id: str) -> None:
        self.url = url
        self.api_key = api_key
        self.server_id = server_id

    async def _authenticate(self, websocket: websockets.WebSocketClientProtocol):
        await websocket.send(
            json.dumps(
                {
                    "type": "auth",
                    "api_key": self.api_key,
                    "server_id": self.server_id,
                }
            )
        )
        response = await websocket.recv()
        return json.loads(response)

    async def connect(self) -> AsyncGenerator[websockets.WebSocketClientProtocol, None]:
        async with websockets.connect(self.url, ping_interval=20, ping_timeout=10) as ws:
            auth_resp = await self._authenticate(ws)
            if auth_resp.get("type") != "auth_ok":
                raise RuntimeError(f"auth failed: {auth_resp}")
            yield ws

    async def send_metrics(
        self, metrics: Dict, websocket: websockets.WebSocketClientProtocol
    ):
        await websocket.send(
            json.dumps(
                {
                    "type": "metrics",
                    "server_id": self.server_id,
                    "data": metrics,
                }
            )
        )
        return json.loads(await websocket.recv())


async def run_probe(
    url: str,
    api_key: str,
    server_id: str,
    interval: int,
    collect_fn: Callable[[], Dict],
):
    client = ProbeClient(url, api_key, server_id)
    while True:
        try:
            async for ws in client.connect():
                while True:
                    payload = collect_fn()
                    await client.send_metrics(payload, ws)
                    await asyncio.sleep(interval)
        except Exception as exc:  # backoff before reconnect
            print(f"[probe] connection error: {exc}")
            await asyncio.sleep(5)
