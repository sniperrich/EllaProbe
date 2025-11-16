import asyncio
import os

from probe.client.ws import run_probe
from probe.collector.system import collect_metrics


def load_env() -> dict:
    return {
        "CONTROL_WS": os.getenv("CONTROL_WS", "ws://localhost:8000/ws/probe"),
        "API_KEY": os.getenv("PROBE_API_KEY", "changeme"),
        "SERVER_ID": os.getenv("SERVER_ID", "server-uuid"),
        "INTERVAL": int(os.getenv("PROBE_INTERVAL", "5")),
    }


def main():
    cfg = load_env()
    print(
        f"[probe] connecting to {cfg['CONTROL_WS']} interval={cfg['INTERVAL']}s server={cfg['SERVER_ID']}"
    )
    asyncio.run(
        run_probe(
            url=cfg["CONTROL_WS"],
            api_key=cfg["API_KEY"],
            server_id=cfg["SERVER_ID"],
            interval=cfg["INTERVAL"],
            collect_fn=collect_metrics,
        )
    )


if __name__ == "__main__":
    main()
