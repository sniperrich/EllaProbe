const params = new URLSearchParams(location.search);
const serverId = params.get("server_id");
const wsStatusEl = document.getElementById("ws-status");

const charts = {};
const datasets = {};
const maxPoints = 120;

function fmtBytes(bytes) {
  if (!bytes && bytes !== 0) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let val = bytes;
  let idx = 0;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(1)} ${units[idx]}`;
}

function fmtRate(bytesPerSec) {
  return fmtBytes(bytesPerSec) + "/s";
}

function card(title, value, sub) {
  return `
    <div class="border border-slate-800 bg-slate-950/60 rounded-lg p-3">
      <p class="text-xs uppercase text-slate-500">${title}</p>
      <p class="text-2xl font-semibold text-white">${value}</p>
      <p class="text-xs text-slate-400">${sub || ""}</p>
    </div>
  `;
}

function renderCards(data) {
  const vpn = data.vpn || {};
  const net = data.network || {};
  const disk = data.disk_io || {};
  const host = data.host || {};
  document.getElementById("stat-cards").innerHTML = `
    ${card("CPU", `${(data.cpu ?? 0).toFixed(1)}%`, "利用率")}
    ${card("内存", `${(data.memory ?? 0).toFixed(1)}%`, "占用")}
    ${card("带宽", `${fmtRate(net.tx_rate || 0)} / ${fmtRate(net.rx_rate || 0)}`, host.iface || "-")}
    ${card("磁盘IO", `${fmtRate(disk.read_rate || 0)} / ${fmtRate(disk.write_rate || 0)}`, "R/W")}
    ${card("VPN连接", `${vpn.connections || 0}`, `OVPN:${vpn.openvpn_running ? "Y" : "N"} WG:${vpn.wireguard_running ? "Y" : "N"}`)}
    ${card("网络累计", `${fmtBytes(net.bytes_sent || 0)} / ${fmtBytes(net.bytes_recv || 0)}`, "TX / RX")}
    ${card("磁盘累计", `${fmtBytes(disk.read_bytes || 0)} / ${fmtBytes(disk.write_bytes || 0)}`, "Read / Write")}
    ${card("主机", host.name || "-", `${host.ip || "-"} @ ${host.iface || "-"}`)}
  `;
}

function ensureChart(id, label, color, yTitle) {
  if (charts[id]) return charts[id];
  const ctx = document.getElementById(id).getContext("2d");
  charts[id] = new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [{ label, data: [], borderColor: color, backgroundColor: color, tension: 0.3 }] },
    options: {
      responsive: true,
      animation: false,
      scales: { y: { title: { display: true, text: yTitle } }, x: { display: false } },
      plugins: { legend: { display: false } },
    },
  });
  return charts[id];
}

function pushPoint(chart, value, ts) {
  chart.data.labels.push(ts);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > maxPoints) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
}

function handleUpdate(msg) {
  const data = msg.data || {};
  renderCards(data);
  const ts = msg.timestamp || new Date().toISOString();

  pushPoint(ensureChart("chart-cpu", "CPU%", "#10b981", "CPU %"), data.cpu ?? 0, ts);
  pushPoint(ensureChart("chart-mem", "Mem%", "#3b82f6", "Mem %"), data.memory ?? 0, ts);

  const net = data.network || {};
  pushPoint(ensureChart("chart-net", "Net TX/RX (MB/s)", "#f59e0b", "MB/s"), ((net.tx_rate || 0) + (net.rx_rate || 0)) / (1024 * 1024), ts);

  const disk = data.disk_io || {};
  pushPoint(ensureChart("chart-disk", "Disk R/W (MB/s)", "#a78bfa", "MB/s"), ((disk.read_rate || 0) + (disk.write_rate || 0)) / (1024 * 1024), ts);

  const vpn = data.vpn || {};
  pushPoint(ensureChart("chart-vpn", "VPN Connections", "#ef4444", "连接数"), vpn.connections || 0, ts);
}

function connectWs() {
  if (!serverId) {
    alert("缺少 server_id 参数");
    return;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = window.BACKEND_WS || `${proto}://${location.hostname}:9000/ws/dashboard`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => (wsStatusEl.textContent = "已连接");
  ws.onclose = () => (wsStatusEl.textContent = "断开");
  ws.onerror = () => (wsStatusEl.textContent = "错误");
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type !== "realtime_update" || msg.server_id !== serverId) return;
    handleUpdate(msg);
  };
}

connectWs();
