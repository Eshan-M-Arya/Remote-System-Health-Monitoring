"""
Latency Tracker module for measuring network and processing latency of UDP health packets.
Supports both monotonic high-resolution timing (local) and wall-clock timestamps.
"""

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Dict, List, Optional


@dataclass
class LatencyStats:
    count: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    last_ms: float = 0.0


class LatencyTracker:
    """Thread-safe latency metrics tracker."""

    def __init__(self, history_size: int = 1000):
        self._history: deque = deque(maxlen=history_size)
        self._node_history: Dict[str, deque] = {}
        self._count = 0
        self._sum_ms = 0.0
        self._min_ms = float("inf")
        self._max_ms = 0.0
        self._last_ms = 0.0
        self._lock = threading.Lock()

    def record(self, latency_ms: float, node_id: Optional[str] = None):
        """Record a single latency measurement in milliseconds."""
        if latency_ms < 0:
            # Compensate for slight clock inaccuracies
            latency_ms = 0.0

        with self._lock:
            self._count += 1
            self._sum_ms += latency_ms
            self._last_ms = latency_ms
            if latency_ms < self._min_ms:
                self._min_ms = latency_ms
            if latency_ms > self._max_ms:
                self._max_ms = latency_ms
            self._history.append(latency_ms)

            if node_id:
                if node_id not in self._node_history:
                    self._node_history[node_id] = deque(maxlen=500)
                self._node_history[node_id].append(latency_ms)

    def get_stats(self) -> LatencyStats:
        """Return aggregate latency statistics."""
        with self._lock:
            if self._count == 0:
                return LatencyStats(count=0, min_ms=0.0, max_ms=0.0, avg_ms=0.0, last_ms=0.0)
            avg = self._sum_ms / self._count
            min_val = self._min_ms if self._min_ms != float("inf") else 0.0
            return LatencyStats(
                count=self._count,
                min_ms=round(min_val, 2),
                max_ms=round(self._max_ms, 2),
                avg_ms=round(avg, 2),
                last_ms=round(self._last_ms, 2),
            )

    def get_recent_samples(self, n: int = 50) -> List[float]:
        """Return the most recent latency samples."""
        with self._lock:
            return list(self._history)[-n:]

    def reset(self):
        """Reset all latency stats."""
        with self._lock:
            self._history.clear()
            self._node_history.clear()
            self._count = 0
            self._sum_ms = 0.0
            self._min_ms = float("inf")
            self._max_ms = 0.0
            self._last_ms = 0.0
