"""
Central Monitoring Server using UDP.
Receives health and alert packets from multiple agents, processes them with logical priority,
tracks node health, detects timeouts, and displays a live terminal dashboard.
"""

import argparse
from datetime import datetime
import json
import os
import queue
import socket
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

# Support imports both when run as a package or directly
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.alert_manager import Alert, AlertManager
from server.latency_tracker import LatencyStats, LatencyTracker
from server.node_manager import NodeManager, NodeState


DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "config.json")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from JSON file or return sensible defaults."""
    defaults = {
        "server": {"host": "127.0.0.1", "port": 5000, "buffer_size": 4096},
        "thresholds": {
            "cpu": {"warning_percent": 80.0, "critical_percent": 90.0},
            "memory": {"warning_percent": 80.0, "critical_percent": 90.0},
        },
        "monitoring": {
            "node_timeout_seconds": 5.0,
            "dashboard_refresh_seconds": 1.0,
            "recent_alerts_limit": 8,
        },
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge loaded config over defaults
                for section, vals in loaded.items():
                    if section in defaults and isinstance(vals, dict):
                        defaults[section].update(vals)
                    else:
                        defaults[section] = vals
        except Exception as e:
            print(f"[WARN] Failed to load {config_path} ({e}), using default configuration.")
    return defaults


class MonitorServer:
    """
    UDP Monitoring Server with application-level priority queuing,
    node state management, and real-time failure detection.
    """

    # Priority mapping for logical queuing: 0 is highest priority
    PRIORITY_MAP = {
        "CRITICAL": 0,
        "WARNING": 1,
        "HEALTH": 2,
    }

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        buffer_size: int = 4096,
        node_timeout: float = 5.0,
        cpu_warning: float = 80.0,
        cpu_critical: float = 90.0,
        memory_warning: float = 80.0,
        memory_critical: float = 90.0,
        dashboard_refresh: float = 1.0,
        recent_alerts_limit: int = 8,
        headless: bool = False,
    ):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.node_timeout = node_timeout
        self.dashboard_refresh = dashboard_refresh
        self.recent_alerts_limit = recent_alerts_limit
        self.headless = headless

        self.node_manager = NodeManager()
        self.alert_manager = AlertManager(
            cpu_warning=cpu_warning,
            cpu_critical=cpu_critical,
            memory_warning=memory_warning,
            memory_critical=memory_critical,
        )
        self.latency_tracker = LatencyTracker()

        # Priority queue holds (priority_int, arrival_counter, packet, addr, arrival_mono, arrival_wall)
        self.packet_queue = queue.PriorityQueue()
        self._arrival_counter = 0

        self.sock: Optional[socket.socket] = None
        self._running = False
        self._threads = []
        self.total_packets_received = 0
        self.total_malformed_packets = 0

    def start(self):
        """Initialize socket and start background worker threads."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow address reuse
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.5)

        self._running = True

        # Thread 1: Socket Receiver
        t_recv = threading.Thread(target=self._receive_loop, name="UDP-Receiver", daemon=True)
        # Thread 2: Priority Packet Processor
        t_proc = threading.Thread(target=self._process_loop, name="Packet-Processor", daemon=True)
        # Thread 3: Timeout Failure Detector
        t_timeout = threading.Thread(target=self._timeout_loop, name="Timeout-Detector", daemon=True)

        self._threads = [t_recv, t_proc, t_timeout]
        for t in self._threads:
            t.start()

        if not self.headless:
            # Thread 4: Dashboard Renderer
            t_dash = threading.Thread(target=self._dashboard_loop, name="Dashboard", daemon=True)
            self._threads.append(t_dash)
            t_dash.start()

    def stop(self):
        """Stop all server operations and close socket."""
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        for t in self._threads:
            t.join(timeout=1.0)

    def _receive_loop(self):
        """Receive UDP datagrams, validate JSON, and place in priority queue."""
        while self._running:
            try:
                data, addr = self.sock.recvfrom(self.buffer_size)
                arrival_mono = time.perf_counter()
                arrival_wall = time.time()
                self.total_packets_received += 1

                try:
                    payload = json.loads(data.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.total_malformed_packets += 1
                    continue

                if not isinstance(payload, dict) or "node_id" not in payload:
                    self.total_malformed_packets += 1
                    continue

                packet_type = str(payload.get("type", "HEALTH")).upper()
                priority = self.PRIORITY_MAP.get(packet_type, 2)

                self._arrival_counter += 1
                self.packet_queue.put((priority, self._arrival_counter, payload, addr, arrival_mono, arrival_wall))

            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                if self._running:
                    print(f"[ERROR] Receiver error: {e}", file=sys.stderr)

    def _process_loop(self):
        """Process datagrams from priority queue in priority order."""
        while self._running:
            try:
                item = self.packet_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            priority, count, payload, addr, arrival_mono, arrival_wall = item
            node_id = str(payload.get("node_id", "UNKNOWN"))

            # Calculate Latency
            # Prefer monotonic time for local experiments to prevent clock drift inaccuracies
            if "send_time_mono" in payload and payload["send_time_mono"] is not None:
                latency_ms = (arrival_mono - float(payload["send_time_mono"])) * 1000.0
            elif "timestamp" in payload and payload["timestamp"] is not None:
                latency_ms = (arrival_wall - float(payload["timestamp"])) * 1000.0
            else:
                latency_ms = 0.0

            self.latency_tracker.record(latency_ms, node_id=node_id)

            # Evaluate thresholds and determine alert
            evaluated_status, alert = self.alert_manager.evaluate_packet(payload)
            reason = alert.message if alert else payload.get("reason", "")

            # Update node state
            self.node_manager.update_node(
                node_id=node_id,
                packet=payload,
                addr=addr,
                evaluated_status=evaluated_status,
                reason=reason,
            )

            self.packet_queue.task_done()

    def _timeout_loop(self):
        """Periodically check for nodes that haven't sent a heartbeat within node_timeout."""
        while self._running:
            time.sleep(0.5)
            timed_out_nodes = self.node_manager.check_timeouts(self.node_timeout)
            for node in timed_out_nodes:
                self.alert_manager.record_failure(
                    node_id=node.node_id,
                    message=f"Node stopped responding (no heartbeat for >{self.node_timeout:.1f}s)",
                )

    def _dashboard_loop(self):
        """Periodically render the terminal monitoring dashboard."""
        while self._running:
            self.render_dashboard()
            time.sleep(self.dashboard_refresh)

    def render_dashboard(self) -> str:
        """Construct and print the terminal dashboard string."""
        nodes = self.node_manager.get_all_nodes()
        active_cnt, total_cnt = self.node_manager.get_counts()
        alerts = self.alert_manager.get_recent_alerts(limit=self.recent_alerts_limit)
        stats = self.latency_tracker.get_stats()

        lines = [
            "============================================================",
            "             REMOTE SYSTEM HEALTH MONITOR (UDP)",
            "============================================================",
            f"Server: {self.host}:{self.port} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"{'NODE':<12} {'CPU':<10} {'MEMORY':<10} {'PROCESSES':<12} {'STATUS':<10}",
            "-" * 60,
        ]

        if not nodes:
            lines.append("  (No reporting nodes connected yet...)")
        else:
            for node_id, state in nodes.items():
                if state.status == "OFFLINE":
                    cpu_str = "--"
                    mem_str = "--"
                    proc_str = "--"
                else:
                    cpu_str = f"{state.cpu_percent:5.1f}%"
                    mem_str = f"{state.memory_percent:5.1f}%"
                    proc_str = f"{state.process_count:<12}"

                lines.append(f"{node_id:<12} {cpu_str:<10} {mem_str:<10} {proc_str} {state.status:<10}")

        lines.extend([
            "-" * 60,
            "",
            "RECENT ALERTS",
        ])

        if not alerts:
            lines.append("  [No alerts recorded]")
        else:
            for a in alerts:
                lines.append(f"  {a}")

        lines.extend([
            "",
            "LATENCY STATISTICS",
            f"  Packets: {stats.count} | Avg: {stats.avg_ms} ms | Min: {stats.min_ms} ms | Max: {stats.max_ms} ms | Last: {stats.last_ms} ms",
            "",
            f"ACTIVE NODES: {active_cnt}/{total_cnt} | TOTAL PACKETS: {self.total_packets_received}",
            "============================================================",
            "",
        ])

        output = "\n".join(lines)
        if not self.headless:
            # Clear screen ANSI code (cross-platform compatible in modern terminals)
            print("\033[H\033[J", end="")
            print(output)
        return output


def main():
    parser = argparse.ArgumentParser(description="Central UDP Health Monitoring Server")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config.json")
    parser.add_argument("--host", default=None, help="Server IP to bind (default from config or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="UDP port to bind (default from config or 5000)")
    parser.add_argument("--timeout", type=float, default=None, help="Node offline timeout in seconds")
    parser.add_argument("--headless", action="store_true", help="Run without live dashboard updating stdout")
    args = parser.parse_args()

    cfg = load_config(args.config)
    server_cfg = cfg.get("server", {})
    threshold_cfg = cfg.get("thresholds", {})
    monitor_cfg = cfg.get("monitoring", {})

    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or server_cfg.get("port", 5000)
    timeout = args.timeout or monitor_cfg.get("node_timeout_seconds", 5.0)

    server = MonitorServer(
        host=host,
        port=port,
        buffer_size=server_cfg.get("buffer_size", 4096),
        node_timeout=timeout,
        cpu_warning=threshold_cfg.get("cpu", {}).get("warning_percent", 80.0),
        cpu_critical=threshold_cfg.get("cpu", {}).get("critical_percent", 90.0),
        memory_warning=threshold_cfg.get("memory", {}).get("warning_percent", 80.0),
        memory_critical=threshold_cfg.get("memory", {}).get("critical_percent", 90.0),
        dashboard_refresh=monitor_cfg.get("dashboard_refresh_seconds", 1.0),
        recent_alerts_limit=monitor_cfg.get("recent_alerts_limit", 8),
        headless=args.headless,
    )

    print(f"[*] Starting UDP Health Monitor Server on {host}:{port} (timeout={timeout}s)...")
    server.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Shutting down server gracefully...")
    finally:
        server.stop()
        print("[*] Server stopped.")


if __name__ == "__main__":
    main()
