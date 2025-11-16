import uvicorn
from fastapi import Depends, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.api import routes
from backend.database.db import Base, engine, get_db
from backend.websocket import server as ws_server

Base.metadata.create_all(bind=engine)

app = FastAPI(title="VPN Probe Control Plane")

app.include_router(routes.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/probe")
async def probe_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await ws_server.probe_socket(websocket, db)


@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await ws_server.dashboard_socket(websocket)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
