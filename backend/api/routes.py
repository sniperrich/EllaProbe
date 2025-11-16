import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from backend.api.schemas import (
    MetricIn,
    MetricsList,
    MetricOut,
    ProbeBootstrapRequest,
    ProbeBootstrapResponse,
    ProbeCreate,
    ProbeOut,
    ServerCreate,
    ServerOut,
)
from backend.database.db import get_db
from backend.models.models import Metric, Probe, Server

router = APIRouter(prefix="/api")


@router.get("/servers", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db)):
    return db.query(Server).all()


@router.post("/servers", response_model=ServerOut, status_code=HTTP_201_CREATED)
def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    item = Server(name=server.name, owner_id=server.owner_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/probes", response_model=ProbeOut, status_code=HTTP_201_CREATED)
def create_probe(probe: ProbeCreate, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == probe.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="server not found")
    item = Probe(server_id=probe.server_id, api_key=probe.api_key)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/metrics/{server_id}", response_model=MetricsList)
def get_metrics(server_id: str, limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Metric)
        .filter(Metric.server_id == server_id)
        .order_by(Metric.timestamp.desc())
        .limit(limit)
        .all()
    )
    return MetricsList(items=list(reversed(rows)))


@router.post("/metrics", response_model=MetricOut, status_code=HTTP_201_CREATED)
def add_metric(metric: MetricIn, db: Session = Depends(get_db)):
    probe = db.query(Probe).filter(Probe.id == metric.probe_id).first()
    if not probe:
        raise HTTPException(status_code=404, detail="probe not found")
    item = Metric(
        server_id=metric.server_id,
        probe_id=metric.probe_id,
        timestamp=metric.timestamp,
        metrics_json=metric.data,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _ensure_server(payload: ProbeBootstrapRequest, db: Session) -> Server:
    if payload.server_id:
        server = db.query(Server).filter(Server.id == payload.server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="server not found")
        return server
    if not payload.server_name:
        raise HTTPException(status_code=400, detail="server_name or server_id required")
    server = Server(name=payload.server_name)
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def _build_script(payload: ProbeBootstrapRequest, server: Server, api_key: str, control_ws: str) -> str:
    if payload.use_docker:
        return f"""#!/usr/bin/env bash
set -e
CONTROL_WS="{control_ws}"
SERVER_ID="{server.id}"
PROBE_API_KEY="{api_key}"
PROBE_INTERVAL="{payload.interval}"

command -v docker >/dev/null 2>&1 || (apt-get update && apt-get install -y docker.io)
docker rm -f ellaprobe-probe || true
docker run -d --name ellaprobe-probe --restart=always \\
  -e PROBE_API_KEY="$PROBE_API_KEY" \\
  -e SERVER_ID="$SERVER_ID" \\
  -e CONTROL_WS="$CONTROL_WS" \\
  -e PROBE_INTERVAL="$PROBE_INTERVAL" \\
  python:3.11-slim bash -c '
    set -e
    apt-get update && apt-get install -y git build-essential python3-dev
    mkdir -p /opt && cd /opt
    git clone https://github.com/sniperrich/EllaProbe.git
    cd EllaProbe/probe
    pip install -r requirements.txt
    python main.py
  '
echo "probe container started. name=ellaprobe-probe"
"""

    return f"""#!/usr/bin/env bash
set -e
CONTROL_HOST="{payload.control_host}"
CONTROL_PORT="{payload.control_port}"
SERVER_ID="{server.id}"
PROBE_API_KEY="{api_key}"
PROBE_INTERVAL="{payload.interval}"
CONTROL_WS="{control_ws}"

command -v python3.11 >/dev/null 2>&1 || (apt-get update && apt-get install -y python3.11 python3.11-venv)
command -v git >/dev/null 2>&1 || (apt-get update && apt-get install -y git)
mkdir -p /opt
cd /opt
if [ ! -d "EllaProbe" ]; then
  git clone https://github.com/sniperrich/EllaProbe.git
fi
cd EllaProbe/probe
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cat > .env <<EOF
PROBE_API_KEY=$PROBE_API_KEY
SERVER_ID=$SERVER_ID
CONTROL_WS=$CONTROL_WS
PROBE_INTERVAL=$PROBE_INTERVAL
EOF
nohup bash -c 'set -a; source .env; set +a; source .venv/bin/activate; python main.py' > /var/log/ellaprobe-probe.log 2>&1 &
echo $! > /var/run/ellaprobe-probe.pid
echo "probe started. logs: /var/log/ellaprobe-probe.log"
"""


@router.post("/probes/bootstrap", response_model=ProbeBootstrapResponse)
def bootstrap_probe(payload: ProbeBootstrapRequest, db: Session = Depends(get_db)):
    server = _ensure_server(payload, db)
    api_key = payload.api_key or secrets.token_hex(16)
    probe = Probe(server_id=server.id, api_key=api_key)
    db.add(probe)
    db.commit()
    db.refresh(probe)

    scheme = "wss" if payload.use_wss else "ws"
    control_ws = f"{scheme}://{payload.control_host}:{payload.control_port}/ws/probe"
    script = _build_script(payload, server, api_key, control_ws)

    return ProbeBootstrapResponse(
        server_id=server.id,
        probe_id=probe.id,
        api_key=api_key,
        control_ws=control_ws,
        script=script,
    )


@router.get("/probes/deploy.sh")
def bootstrap_script(
    control_host: str,
    server_name: str = "vpn-node",
    control_port: int = 9000,
    use_wss: bool = False,
    interval: int = 5,
    use_docker: bool = False,
    server_id: str | None = None,
    api_key: str | None = None,
    db: Session = Depends(get_db),
):
    payload = ProbeBootstrapRequest(
        server_id=server_id,
        server_name=server_name,
        control_host=control_host,
        control_port=control_port,
        use_wss=use_wss,
        interval=interval,
        api_key=api_key,
        use_docker=use_docker,
    )
    server = _ensure_server(payload, db)
    api_key_value = payload.api_key or secrets.token_hex(16)
    probe = Probe(server_id=server.id, api_key=api_key_value)
    db.add(probe)
    db.commit()
    db.refresh(probe)

    scheme = "wss" if payload.use_wss else "ws"
    control_ws = f"{scheme}://{payload.control_host}:{payload.control_port}/ws/probe"
    script = _build_script(payload, server, api_key_value, control_ws)

    return Response(content=script, media_type="text/plain")
