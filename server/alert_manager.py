"""
Alert Manager module for evaluating incoming metrics against configurable thresholds,
recording alerts, and maintaining an alert history.
"""

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Deque, Dict, List, Optional, Tuple


@dataclass
class Alert:
    timestamp: float
    severity: str  # 'CRITICAL', 'WARNING', 'FAILURE', 'INFO', 'RECOVERY'
    node_id: str
    message: str

    def formatted_time(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))

    def __str__(self) -> str:
        return f"[{self.severity}] {self.node_id} - {self.message} ({self.formatted_time()})"


class AlertManager:
    """Evaluates node metrics against thresholds and records system alerts."""

    def __init__(
        self,
        cpu_warning: float = 80.0,
        cpu_critical: float = 90.0,
        memory_warning: float = 80.0,
        memory_critical: float = 90.0,
        max_history: int = 100,
    ):
        self.cpu_warning = float(cpu_warning)
        self.cpu_critical = float(cpu_critical)
        self.memory_warning = float(memory_warning)
        self.memory_critical = float(memory_critical)
        self._history: Deque[Alert] = deque(maxlen=max_history)
        self._lock = threading.Lock()
        # Track previous status per node to prevent spamming duplicate alerts on every single packet
        self._previous_status: Dict[str, str] = {}

    def evaluate_packet(self, packet: dict) -> Tuple[str, Optional[Alert]]:
        """
        Evaluate an incoming packet. Returns (evaluated_status, optional_new_alert).
        Evaluated status will be 'CRITICAL', 'WARNING', or 'ONLINE'.
        """
        node_id = packet.get("node_id", "UNKNOWN")
        packet_type = packet.get("type", "HEALTH").upper()
        cpu = float(packet.get("cpu_percent", 0.0))
        mem = float(packet.get("memory_percent", 0.0))
        reason = packet.get("reason", "")

        status = "ONLINE"
        alert_severity = None
        alert_msg = ""

        # Check critical condition first
        if packet_type == "CRITICAL":
            status = "CRITICAL"
            alert_severity = "CRITICAL"
            alert_msg = reason or f"Critical alert received (CPU={cpu:.1f}%, Mem={mem:.1f}%)"
        elif cpu >= self.cpu_critical:
            status = "CRITICAL"
            alert_severity = "CRITICAL"
            alert_msg = f"CPU exceeded critical threshold: {cpu:.1f}% >= {self.cpu_critical:.1f}%"
        elif mem >= self.memory_critical:
            status = "CRITICAL"
            alert_severity = "CRITICAL"
            alert_msg = f"Memory exceeded critical threshold: {mem:.1f}% >= {self.memory_critical:.1f}%"
        # Check warning condition next
        elif packet_type == "WARNING":
            status = "WARNING"
            alert_severity = "WARNING"
            alert_msg = reason or f"Warning alert received (CPU={cpu:.1f}%, Mem={mem:.1f}%)"
        elif cpu >= self.cpu_warning:
            status = "WARNING"
            alert_severity = "WARNING"
            alert_msg = f"CPU exceeded warning threshold: {cpu:.1f}% >= {self.cpu_warning:.1f}%"
        elif mem >= self.memory_warning:
            status = "WARNING"
            alert_severity = "WARNING"
            alert_msg = f"Memory exceeded warning threshold: {mem:.1f}% >= {self.memory_warning:.1f}%"
        else:
            status = "ONLINE"

        alert = None
        with self._lock:
            prev_status = self._previous_status.get(node_id, "NEW")
            # Generate alert when status changes or when explicit CRITICAL/WARNING packet arrives
            if status != prev_status or packet_type in ("CRITICAL", "WARNING"):
                if alert_severity:
                    alert = Alert(
                        timestamp=time.time(),
                        severity=alert_severity,
                        node_id=node_id,
                        message=alert_msg,
                    )
                    self._history.append(alert)
                elif prev_status in ("WARNING", "CRITICAL", "OFFLINE") and status == "ONLINE":
                    alert = Alert(
                        timestamp=time.time(),
                        severity="RECOVERY",
                        node_id=node_id,
                        message="Node returned to normal health",
                    )
                    self._history.append(alert)

            self._previous_status[node_id] = status

        return status, alert

    def record_failure(self, node_id: str, message: str = "Node stopped responding (offline)") -> Alert:
        """Record node failure alert when node heartbeat times out."""
        with self._lock:
            self._previous_status[node_id] = "OFFLINE"
            alert = Alert(
                timestamp=time.time(),
                severity="FAILURE",
                node_id=node_id,
                message=message,
            )
            self._history.append(alert)
            return alert

    def record_custom_alert(self, severity: str, node_id: str, message: str) -> Alert:
        """Record an arbitrary alert."""
        with self._lock:
            alert = Alert(
                timestamp=time.time(),
                severity=severity,
                node_id=node_id,
                message=message,
            )
            self._history.append(alert)
            return alert

    def get_recent_alerts(self, limit: int = 10) -> List[Alert]:
        """Return the most recent alerts (most recent first)."""
        with self._lock:
            alerts = list(self._history)
            alerts.reverse()
            return alerts[:limit]

    def clear(self):
        """Clear alert history."""
        with self._lock:
            self._history.clear()
            self._previous_status.clear()
