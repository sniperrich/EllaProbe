# VPN 服务器探针监控（适中版）

## 结构
- `backend/` FastAPI 控制面（REST + WebSocket）
- `probe/` 探针客户端（psutil/netifaces 收集 + WebSocket 上报）
- `frontend/` 简单仪表板（Tailwind + Chart.js）

## 快速开始
1. **后端依赖**
   ```bash
   cd vpn-probe/backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn backend.main:app --reload
   ```
   - 数据库默认 `sqlite:///./vpn_probe.db`，通过 `DATABASE_URL` 指向 PostgreSQL。

2. **初始化数据**
   - 创建服务器：
     ```bash
     curl -X POST http://localhost:8000/api/servers -H "Content-Type: application/json" \
       -d '{"name":"vpn-node-1"}'
     ```
   - 创建探针：
     ```bash
     curl -X POST http://localhost:8000/api/probes -H "Content-Type: application/json" \
       -d '{"server_id":"<上一步返回的id>","api_key":"my-probe-key"}'
     ```

3. **运行探针**
   ```bash
   cd vpn-probe/probe
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   PROBE_API_KEY=my-probe-key SERVER_ID=<server-id> CONTROL_WS=ws://127.0.0.1:8000/ws/probe python main.py
   ```
   - 环境变量：`PROBE_INTERVAL`（秒，默认 5）。

4. **前端**
   - 启动后端后，直接打开 `frontend/index.html`（或用 Nginx/静态服务器托管）。
   - WebSocket 地址默认指向同一主机的 `/ws/dashboard`。

## 通信协议
- 探针连接：
  ```json
  {"type":"auth","api_key":"<key>","server_id":"<uuid>"}
  ```
- 上报：
  ```json
  {"type":"metrics","server_id":"<uuid>","data":{...}}
  ```
- 控制面推送给前端：
  ```json
  {"type":"realtime_update","server_id":"<uuid>","data":{...},"timestamp":"..."}
  ```

## TODO
- JWT/用户管理与 API Key 下发
- 指标归档与告警策略
- 使用 Redis / Postgres 流做实时分发
