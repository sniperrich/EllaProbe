import socket
from typing import Dict, Optional

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
    cpu = psutil.cpu_percent(interval=0.3)
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

    return {
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv},
        "vpn": {
            "connections": _vpn_connections(),
            "openvpn_running": vpn_state["openvpn"],
            "wireguard_running": vpn_state["wireguard"],
        },
        "host": {"name": hostname, "ip": ip_addr, "iface": iface},
    }
