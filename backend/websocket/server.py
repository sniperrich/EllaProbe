import datetime as dt
from typing import Dict, Optional

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.models.models import Metric, Probe
from backend.websocket.manager import ConnectionManager

frontend_manager = ConnectionManager()


async def _handle_metrics(
    payload: Dict, probe: Probe, websocket: WebSocket, db: Session
) -> Optional[Metric]:
    data = payload.get("data") or {}
    timestamp = payload.get("timestamp")
    ts = dt.datetime.fromisoformat(timestamp) if timestamp else dt.datetime.utcnow()
    metric_row = Metric(
        server_id=probe.server_id,
        probe_id=probe.id,
        timestamp=ts,
        metrics_json=data,
    )
    db.add(metric_row)
    probe.last_seen = dt.datetime.utcnow()
    db.commit()
    db.refresh(metric_row)
    await frontend_manager.broadcast(
        {
            "type": "realtime_update",
            "server_id": probe.server_id,
            "data": data,
            "timestamp": ts.isoformat(),
        }
    )
    await websocket.send_json({"type": "ack", "timestamp": ts.isoformat()})
    return metric_row


async def probe_socket(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    probe: Optional[Probe] = None
    try:
        auth_msg = await websocket.receive_json()
        if auth_msg.get("type") != "auth":
            await websocket.close(code=4001)
            return
        api_key = auth_msg.get("api_key")
        probe = db.query(Probe).filter(Probe.api_key == api_key).first()
        if not probe:
            await websocket.send_json({"error": "invalid api_key"})
            await websocket.close(code=4003)
            return
        await websocket.send_json({"type": "auth_ok", "probe_id": probe.id})
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "metrics":
                await _handle_metrics(message, probe, websocket, db)
            else:
                await websocket.send_json({"warning": f"unknown type {msg_type}"})
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011)


async def dashboard_socket(websocket: WebSocket):
    await frontend_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive; data is push-only
    except WebSocketDisconnect:
        frontend_manager.disconnect(websocket)
