from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from backend.api.schemas import (
    MetricIn,
    MetricsList,
    MetricOut,
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
