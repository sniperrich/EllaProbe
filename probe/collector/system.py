import socket
import time
from typing import Dict, Optional, Tuple

import netifaces
import psutil


def _vpn_process_running() -> Dict[str, bool]:
    names = {"openvpn": False, "wireguard": False}
    for proc in psutil.process_iter(attrs=["name"]):
        name = (proc.info.get("name") or "").lower()
        if "openvpn" in name:
            names["openvpn"] = True
        if name in {"wg", "wireguard"}:
            names["wireguard"] = True
    return names


def _vpn_connections() -> int:
    count = 0
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == psutil.CONN_ESTABLISHED:
            count += 1
    return count


def _default_gateway_interface() -> Optional[str]:
    gws = netifaces.gateways()
    default = gws.get("default")
    if not default:
        return None
    iface = default.get(netifaces.AF_INET)
    return iface[1] if iface else None


def collect_metrics() -> Dict:
    cpu = psutil.cpu_percent(interval=0.2)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    net = psutil.net_io_counters()
    hostname = socket.gethostname()

    iface = _default_gateway_interface()
    ip_addr = None
    if iface:
        try:
            addr_info = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
            if addr_info:
                ip_addr = addr_info[0].get("addr")
        except Exception:
            ip_addr = None

    vpn_state = _vpn_process_running()

    # 速率计算：以进程内静态缓存保存上次计数与时间
    now = time.time()
    if not hasattr(collect_metrics, "_last"):
        collect_metrics._last = {
            "time": now,
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "disk_read": psutil.disk_io_counters().read_bytes,
            "disk_write": psutil.disk_io_counters().write_bytes,
        }
    last = collect_metrics._last
    interval = max(now - last["time"], 1e-3)
    net_sent_rate = max(net.bytes_sent - last["bytes_sent"], 0) / interval
    net_recv_rate = max(net.bytes_recv - last["bytes_recv"], 0) / interval
    disk_io = psutil.disk_io_counters()
    disk_read_rate = max(disk_io.read_bytes - last["disk_read"], 0) / interval
    disk_write_rate = max(disk_io.write_bytes - last["disk_write"], 0) / interval
    collect_metrics._last = {
        "time": now,
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "disk_read": disk_io.read_bytes,
        "disk_write": disk_io.write_bytes,
    }

    return {
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "tx_rate": net_sent_rate,  # bytes/s
            "rx_rate": net_recv_rate,
            "iface": iface,
            "ip": ip_addr,
        },
        "disk_io": {
            "read_bytes": disk_io.read_bytes,
            "write_bytes": disk_io.write_bytes,
            "read_rate": disk_read_rate,  # bytes/s
            "write_rate": disk_write_rate,
        },
        "vpn": {
            "connections": _vpn_connections(),
            "openvpn_running": vpn_state["openvpn"],
            "wireguard_running": vpn_state["wireguard"],
        },
        "host": {"name": hostname, "ip": ip_addr, "iface": iface},
    }
