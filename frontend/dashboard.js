window.BACKEND_WS = "ws://96.126.191.17:9000/ws/dashboard";
const wsStatusEl = document.getElementById("ws-status");
const gridEl = document.getElementById("server-grid");
const selectEl = document.getElementById("server-select");
const chartCtx = document.getElementById("metrics-chart").getContext("2d");
const controlHostInput = document.getElementById("control-host");
const controlPortInput = document.getElementById("control-port");
const serverNameInput = document.getElementById("server-name");
const intervalInput = document.getElementById("probe-interval");
const useWssInput = document.getElementById("use-wss");
const useDockerInput = document.getElementById("use-docker");
const genBtn = document.getElementById("gen-script");
const copyBtn = document.getElementById("copy-script");
const scriptOutput = document.getElementById("script-output");
const scriptStatus = document.getElementById("script-status");

controlHostInput.value = location.hostname || "127.0.0.1";

const state = {
  servers: {},
  datasets: {},
};

const chart = new Chart(chartCtx, {
  type: "line",
  data: {
    labels: [],
    datasets: [],
  },
  options: {
    responsive: true,
    animation: false,
    scales: {
      y: {
        title: { display: true, text: "CPU %" },
        min: 0,
        max: 100,
      },
      x: { display: true },
    },
    plugins: {
      legend: { display: true },
    },
  },
});

function upsertDataset(serverId) {
  if (!state.datasets[serverId]) {
    const color = `hsl(${Math.floor(Math.random() * 360)}, 70%, 60%)`;
    const ds = {
      label: serverId,
      data: [],
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
    };
    state.datasets[serverId] = ds;
    chart.data.datasets.push(ds);
    selectEl.insertAdjacentHTML(
      "beforeend",
      `<option value="${serverId}">${serverId}</option>`
    );
  }
  return state.datasets[serverId];
}

function renderServerCard(serverId, data) {
  let card = document.getElementById(`server-${serverId}`);
  const vpn = data.vpn || {};
  const network = data.network || {};
  if (!card) {
    card = document.createElement("div");
    card.id = `server-${serverId}`;
    card.className =
      "card border border-slate-800 bg-slate-950/60 rounded-xl p-4 flex flex-col gap-2";
    gridEl.appendChild(card);
  }
  card.innerHTML = `
    <div class="flex items-center justify-between">
      <div>
        <p class="text-xs uppercase text-slate-500">Server</p>
        <h3 class="text-xl font-semibold">${serverId}</h3>
      </div>
      <span class="text-emerald-400 text-sm bg-emerald-400/10 px-2 py-1 rounded-full">在线</span>
    </div>
    <div class="grid grid-cols-2 gap-2 text-sm text-slate-300">
      <div>CPU: <span class="text-white">${Number(data.cpu || 0).toFixed(
        1
      )}%</span></div>
      <div>内存: <span class="text-white">${Number(data.memory || 0).toFixed(
        1
      )}%</span></div>
      <div>磁盘: <span class="text-white">${Number(data.disk || 0).toFixed(
        1
      )}%</span></div>
      <div>VPN 连接: <span class="text-white">${vpn.connections || 0}</span></div>
      <div>网络出: ${network.bytes_sent || 0}</div>
      <div>网络入: ${network.bytes_recv || 0}</div>
    </div>
    <p class="text-xs text-slate-500">接口: ${
      data.host?.iface || "-"
    } | IP: ${data.host?.ip || "-"}</p>
  `;
}

function updateChart(serverId, cpu, timestamp) {
  const target = selectEl.value || serverId;
  if (target !== serverId) return;

  const ds = upsertDataset(serverId);
  chart.data.labels.push(timestamp);
  ds.data.push(cpu);
  if (chart.data.labels.length > 50) {
    chart.data.labels.shift();
    ds.data.shift();
  }
  chart.update();
}

async function generateScript() {
  const host = controlHostInput.value.trim() || location.hostname;
  const port = Number(controlPortInput.value || 9000);
  const serverName = serverNameInput.value.trim() || "vpn-node";
  const interval = Number(intervalInput.value || 5);
  const useWss = useWssInput.checked;
  const useDocker = useDockerInput.checked;
  const scheme = useWss ? "https" : "http";
  scriptStatus.textContent = "生成中...";
  try {
    const resp = await fetch(`${scheme}://${host}:${port}/api/probes/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        server_name: serverName,
        control_host: host,
        control_port: port,
        use_wss: useWss,
        interval,
        use_docker: useDocker,
      }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || resp.statusText);
    }
    const data = await resp.json();
    scriptOutput.value = data.script;
    scriptStatus.textContent = `已生成，server_id=${data.server_id}`;
  } catch (err) {
    scriptStatus.textContent = `失败: ${err.message}`;
  }
}

async function copyScript() {
  if (!scriptOutput.value) {
    scriptStatus.textContent = "没有可复制的脚本";
    return;
  }
  try {
    await navigator.clipboard.writeText(scriptOutput.value);
    scriptStatus.textContent = "已复制";
  } catch (_e) {
    scriptStatus.textContent = "复制失败";
  }
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  // 若前端与后端不同端口，通过 BACKEND_WS 覆盖；默认使用当前主机的 9000 端口
  const wsUrl =
    window.BACKEND_WS ||
    `${proto}://${location.hostname}:9000/ws/dashboard`;
  const ws = new WebSocket(wsUrl);
  wsStatusEl.textContent = "连接中...";

  ws.onopen = () => {
    wsStatusEl.textContent = "已连接";
  };

  ws.onclose = () => {
    wsStatusEl.textContent = "断开，重连...";
    setTimeout(connectWs, 3000);
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type !== "realtime_update") return;
    const serverId = msg.server_id;
    state.servers[serverId] = msg.data;
    renderServerCard(serverId, msg.data);
    updateChart(serverId, msg.data.cpu ?? 0, msg.timestamp);
  };
}

connectWs();
genBtn?.addEventListener("click", generateScript);
copyBtn?.addEventListener("click", copyScript);
