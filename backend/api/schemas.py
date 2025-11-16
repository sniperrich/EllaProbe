import datetime as dt
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServerCreate(BaseModel):
    name: str
    owner_id: Optional[int] = None


class ServerOut(BaseModel):
    id: str
    name: str
    owner_id: Optional[int] = None

    class Config:
        orm_mode = True


class ProbeCreate(BaseModel):
    server_id: str
    api_key: str = Field(..., min_length=6)


class ProbeOut(BaseModel):
    id: str
    server_id: str
    api_key: str
    last_seen: Optional[dt.datetime]

    class Config:
        orm_mode = True


class MetricIn(BaseModel):
    server_id: str
    probe_id: str
    timestamp: Optional[dt.datetime] = None
    data: Dict[str, Any]


class MetricOut(BaseModel):
    id: int
    timestamp: dt.datetime
    server_id: str
    probe_id: str
    metrics_json: Dict[str, Any]

    class Config:
        orm_mode = True


class MetricsList(BaseModel):
    items: List[MetricOut]


class ProbeBootstrapRequest(BaseModel):
    server_id: Optional[str] = None
    server_name: Optional[str] = None
    control_host: str
    control_port: int = 9000
    use_wss: bool = False
    interval: int = 5
    api_key: Optional[str] = None


class ProbeBootstrapResponse(BaseModel):
    server_id: str
    probe_id: str
    api_key: str
    control_ws: str
    script: str
