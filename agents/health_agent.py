"""
Health Reporting Agent for Remote System Health Monitoring.
Collects system statistics using psutil and sends JSON telemetry packets over UDP.
Supports threshold detection, immediate critical alerts, and failure simulation.
"""

import argparse
from datetime import datetime
import json
import os
import socket
import sys
import time
from typing import Any, Dict, Optional, Tuple

# Support imports both when run as a package or directly
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    import psutil
except ImportError:
    psutil = None

DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "config.json")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from JSON file or return defaults."""
    defaults = {
        "server": {"host": "127.0.0.1", "port": 5000},
        "thresholds": {
            "cpu": {"warning_percent": 80.0, "critical_percent": 90.0},
            "memory": {"warning_percent": 80.0, "critical_percent": 90.0},
        },
        "agent": {
            "report_interval_seconds": 1.0,
            "default_node_id": "NODE-01",
        },
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for section, vals in loaded.items():
                    if section in defaults and isinstance(vals, dict):
                        defaults[section].update(vals)
                    else:
                        defaults[section] = vals
        except Exception:
            pass
    return defaults


class HealthAgent:
    """
    Simulated/Physical server agent transmitting system health over UDP.
    """

    def __init__(
        self,
        node_id: str = "NODE-01",
        server_host: str = "127.0.0.1",
        server_port: int = 5000,
        interval: float = 1.0,
        cpu_warning: float = 80.0,
        cpu_critical: float = 90.0,
        memory_warning: float = 80.0,
        memory_critical: float = 90.0,
        simulate_cpu: Optional[float] = None,
        simulate_memory: Optional[float] = None,
    ):
        self.node_id = node_id
        self.server_host = server_host
        self.server_port = server_port
        self.interval = float(interval)
        self.cpu_warning = float(cpu_warning)
        self.cpu_critical = float(cpu_critical)
        self.memory_warning = float(memory_warning)
        self.memory_critical = float(memory_critical)

        # Simulation overrides
        self.simulate_cpu = simulate_cpu
        self.simulate_memory = simulate_memory

        self.sequence = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._running = False
        self._in_critical_state = False

        # Prime psutil cpu measurement
        if psutil:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current system statistics."""
        # Simulated or actual CPU
        if self.simulate_cpu is not None:
            cpu = float(self.simulate_cpu)
        elif psutil:
            try:
                cpu = float(psutil.cpu_percent(interval=None))
            except Exception:
                cpu = 0.0
        else:
            cpu = 15.0

        # Simulated or actual Memory
        if self.simulate_memory is not None:
            mem = float(self.simulate_memory)
        elif psutil:
            try:
                mem = float(psutil.virtual_memory().percent)
            except Exception:
                mem = 0.0
        else:
            mem = 30.0

        # Process count
        if psutil:
            try:
                process_count = len(psutil.pids())
            except Exception:
                process_count = 100
        else:
            process_count = 100

        # Network statistics
        network = {"bytes_sent": 0, "bytes_recv": 0}
        if psutil:
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    network["bytes_sent"] = net_io.bytes_sent
                    network["bytes_recv"] = net_io.bytes_recv
            except Exception:
                pass

        return {
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(mem, 1),
            "process_count": process_count,
            "network": network,
        }

    def determine_packet_type(self, metrics: Dict[str, Any]) -> Tuple[str, str]:
        """Determine packet type (HEALTH, WARNING, CRITICAL) based on metrics and thresholds."""
        cpu = metrics["cpu_percent"]
        mem = metrics["memory_percent"]

        if cpu >= self.cpu_critical:
            return "CRITICAL", f"CPU critical: {cpu:.1f}% >= {self.cpu_critical:.1f}%"
        if mem >= self.memory_critical:
            return "CRITICAL", f"Memory critical: {mem:.1f}% >= {self.memory_critical:.1f}%"
        if cpu >= self.cpu_warning:
            return "WARNING", f"CPU warning: {cpu:.1f}% >= {self.cpu_warning:.1f}%"
        if mem >= self.memory_warning:
            return "WARNING", f"Memory warning: {mem:.1f}% >= {self.memory_warning:.1f}%"

        return "HEALTH", "Normal"

    def build_packet(
        self,
        packet_type: str = "HEALTH",
        metrics: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> dict:
        """Construct a standardized JSON telemetry packet."""
        self.sequence += 1
        if metrics is None:
            metrics = self.collect_metrics()

        packet = {
            "type": packet_type,
            "node_id": self.node_id,
            "sequence": self.sequence,
            "timestamp": time.time(),
            "send_time_mono": time.perf_counter(),
            "cpu_percent": metrics["cpu_percent"],
            "memory_percent": metrics["memory_percent"],
            "process_count": metrics["process_count"],
            "network": metrics["network"],
        }
        if reason:
            packet["reason"] = reason

        return packet

    def send_packet(self, packet: dict) -> bool:
        """Serialize to JSON and transmit via UDP."""
        try:
            data = json.dumps(packet).encode("utf-8")
            self.sock.sendto(data, (self.server_host, self.server_port))
            return True
        except Exception as e:
            print(f"[{self.node_id}] [ERROR] Failed to send packet: {e}", file=sys.stderr)
            return False

    def send_critical_alert(self, reason: str = "Immediate Critical Alert Triggered"):
        """
        Immediately send a high-priority CRITICAL alert packet,
        bypassing the normal reporting interval.
        """
        metrics = self.collect_metrics()
        packet = self.build_packet(packet_type="CRITICAL", metrics=metrics, reason=reason)
        print(f"[{self.node_id}] >>> [ALERT] Sending IMMEDIATE CRITICAL packet (seq={packet['sequence']}): {reason}")
        self.send_packet(packet)

    def run(
        self,
        max_packets: Optional[int] = None,
        stop_after_seconds: Optional[float] = None,
        verbose: bool = True,
    ):
        """
        Main reporting loop. Periodically sends health packets.
        If a critical condition is encountered, sends an immediate alert packet.
        """
        self._running = True
        start_time = time.time()
        packets_sent = 0

        if verbose:
            print(f"[{self.node_id}] Starting health agent -> {self.server_host}:{self.server_port}")
            print(f"[{self.node_id}] Reporting interval: {self.interval:.1f}s | Warnings: CPU>={self.cpu_warning}%, Mem>={self.memory_warning}% | Critical: CPU>={self.cpu_critical}%, Mem>={self.memory_critical}%")

        try:
            while self._running:
                loop_start = time.time()

                # Check failure simulation limits
                if stop_after_seconds and (loop_start - start_time) >= stop_after_seconds:
                    if verbose:
                        print(f"[{self.node_id}] [SIMULATION] Simulated node failure: stopping after {stop_after_seconds:.1f}s.")
                    break

                if max_packets and packets_sent >= max_packets:
                    if verbose:
                        print(f"[{self.node_id}] Completed sending {max_packets} packets.")
                    break

                metrics = self.collect_metrics()
                packet_type, reason = self.determine_packet_type(metrics)

                # Prioritize critical traffic:
                # If a critical condition was just detected, trigger an immediate alert packet
                if packet_type == "CRITICAL" and not self._in_critical_state:
                    self._in_critical_state = True
                    self.send_critical_alert(reason=f"Threshold breach: {reason}")
                    packets_sent += 1
                elif packet_type != "CRITICAL":
                    self._in_critical_state = False

                # Regular periodic packet
                packet = self.build_packet(packet_type=packet_type, metrics=metrics, reason=reason)
                self.send_packet(packet)
                packets_sent += 1

                if verbose:
                    print(
                        f"[{self.node_id}] Sent #{packet['sequence']} [{packet['type']}] - "
                        f"CPU: {metrics['cpu_percent']}% | Mem: {metrics['memory_percent']}% | "
                        f"Procs: {metrics['process_count']} | Net: ↑{metrics['network']['bytes_sent']}B ↓{metrics['network']['bytes_recv']}B"
                    )

                # Sleep for interval, compensating for loop processing time
                elapsed = time.time() - loop_start
                sleep_time = max(0.05, self.interval - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            if verbose:
                print(f"\n[{self.node_id}] Agent stopped by user.")
        finally:
            self.close()

    def close(self):
        """Close UDP socket."""
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="UDP Health Monitoring Agent")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config.json")
    parser.add_argument("--node-id", default=None, help="Unique Node ID (e.g. NODE-01)")
    parser.add_argument("--host", default=None, help="Server host (default from config or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Server UDP port (default from config or 5000)")
    parser.add_argument("--interval", type=float, default=None, help="Reporting interval in seconds")
    parser.add_argument("--count", type=int, default=None, help="Max number of packets to send before stopping")
    parser.add_argument("--simulate-failure", action="store_true", help="Simulate failure by stopping after 5 reports")
    parser.add_argument("--stop-after", type=float, default=None, help="Stop sending packets after N seconds")
    parser.add_argument("--simulate-cpu", type=float, default=None, help="Simulate a specific CPU percentage (e.g. 95)")
    parser.add_argument("--simulate-memory", type=float, default=None, help="Simulate a specific Memory percentage")
    parser.add_argument("--trigger-critical", action="store_true", help="Force an immediate critical alert at startup")
    parser.add_argument("--quiet", action="store_true", help="Disable per-packet console output")
    args = parser.parse_args()

    cfg = load_config(args.config)
    server_cfg = cfg.get("server", {})
    agent_cfg = cfg.get("agent", {})
    threshold_cfg = cfg.get("thresholds", {})

    node_id = args.node_id or agent_cfg.get("default_node_id", "NODE-01")
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or server_cfg.get("port", 5000)
    interval = args.interval or agent_cfg.get("report_interval_seconds", 1.0)

    agent = HealthAgent(
        node_id=node_id,
        server_host=host,
        server_port=port,
        interval=interval,
        cpu_warning=threshold_cfg.get("cpu", {}).get("warning_percent", 80.0),
        cpu_critical=threshold_cfg.get("cpu", {}).get("critical_percent", 90.0),
        memory_warning=threshold_cfg.get("memory", {}).get("warning_percent", 80.0),
        memory_critical=threshold_cfg.get("memory", {}).get("critical_percent", 90.0),
        simulate_cpu=args.simulate_cpu,
        simulate_memory=args.simulate_memory,
    )

    max_packets = args.count
    if args.simulate_failure and max_packets is None and args.stop_after is None:
        max_packets = 5

    if args.trigger_critical:
        agent.send_critical_alert("Manual critical trigger requested via CLI")

    agent.run(
        max_packets=max_packets,
        stop_after_seconds=args.stop_after,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
