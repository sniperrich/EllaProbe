import datetime as dt
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, JSON, Integer
from sqlalchemy.orm import relationship

from backend.database.db import Base


def default_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)

    servers = relationship("Server", back_populates="owner")


class Server(Base):
    __tablename__ = "servers"

    id = Column(String(36), primary_key=True, default=default_uuid)
    name = Column(String(128), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="servers")
    probes = relationship("Probe", back_populates="server")
    metrics = relationship("Metric", back_populates="server", order_by="desc(Metric.timestamp)")


class Probe(Base):
    __tablename__ = "probes"

    id = Column(String(36), primary_key=True, default=default_uuid)
    server_id = Column(String(36), ForeignKey("servers.id"), nullable=False)
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    last_seen = Column(DateTime, default=dt.datetime.utcnow, nullable=True)

    server = relationship("Server", back_populates="probes")
    metrics = relationship("Metric", back_populates="probe", order_by="desc(Metric.timestamp)")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=dt.datetime.utcnow, index=True)
    probe_id = Column(String(36), ForeignKey("probes.id"), nullable=False)
    server_id = Column(String(36), ForeignKey("servers.id"), nullable=False)
    metrics_json = Column(JSON, nullable=False)

    probe = relationship("Probe", back_populates="metrics")
    server = relationship("Server", back_populates="metrics")
