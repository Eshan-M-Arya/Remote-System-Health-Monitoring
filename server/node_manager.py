"""
Node Manager module for tracking states of all reporting agent nodes.
Maintains state in memory, updates metrics on incoming packets, and detects offline nodes.
"""

from dataclasses import dataclass, field
import threading
import time
from typing import Dict, List, Optional, Tuple


@dataclass
class NodeState:
    node_id: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    process_count: int = 0
    network: dict = field(default_factory=lambda: {"bytes_sent": 0, "bytes_recv": 0})
    status: str = "ONLINE"
    last_heartbeat: float = 0.0
    last_sequence: int = -1
    total_packets: int = 0
    last_addr: Optional[Tuple[str, int]] = None
    last_packet_type: str = "HEALTH"
    reason: str = ""


class NodeManager:
    """Thread-safe manager for tracking connected nodes and their health states."""

    def __init__(self):
        self._nodes: Dict[str, NodeState] = {}
        self._lock = threading.Lock()

    def update_node(
        self,
        node_id: str,
        packet: dict,
        addr: Optional[Tuple[str, int]] = None,
        evaluated_status: str = "ONLINE",
        reason: str = "",
    ) -> Tuple[NodeState, bool]:
        """
        Update the state of a node from an incoming packet.
        Returns the updated NodeState and a boolean indicating if this is a newly discovered node.
        """
        now = time.time()
        is_new_node = False

        with self._lock:
            if node_id not in self._nodes:
                self._nodes[node_id] = NodeState(node_id=node_id)
                is_new_node = True

            node = self._nodes[node_id]
            node.cpu_percent = float(packet.get("cpu_percent", node.cpu_percent))
            node.memory_percent = float(packet.get("memory_percent", node.memory_percent))
            node.process_count = int(packet.get("process_count", node.process_count))
            node.network = packet.get("network", node.network)
            node.last_sequence = int(packet.get("sequence", node.last_sequence))
            node.last_packet_type = packet.get("type", "HEALTH")
            node.status = evaluated_status
            node.reason = reason
            node.last_heartbeat = now
            node.total_packets += 1
            if addr:
                node.last_addr = addr

            # Return a copy or snapshot to avoid concurrent mutations during rendering
            snapshot = NodeState(
                node_id=node.node_id,
                cpu_percent=node.cpu_percent,
                memory_percent=node.memory_percent,
                process_count=node.process_count,
                network=dict(node.network),
                status=node.status,
                last_heartbeat=node.last_heartbeat,
                last_sequence=node.last_sequence,
                total_packets=node.total_packets,
                last_addr=node.last_addr,
                last_packet_type=node.last_packet_type,
                reason=node.reason,
            )

        return snapshot, is_new_node

    def check_timeouts(self, timeout_seconds: float) -> List[NodeState]:
        """
        Check for nodes that have not reported within the timeout window.
        Transitions their status to 'OFFLINE' and returns the list of newly timed-out nodes.
        """
        now = time.time()
        timed_out_nodes: List[NodeState] = []

        with self._lock:
            for node in self._nodes.values():
                if node.status != "OFFLINE":
                    if (now - node.last_heartbeat) > timeout_seconds:
                        node.status = "OFFLINE"
                        node.reason = f"No heartbeat for >{timeout_seconds:.1f}s"
                        timed_out_nodes.append(
                            NodeState(
                                node_id=node.node_id,
                                cpu_percent=node.cpu_percent,
                                memory_percent=node.memory_percent,
                                process_count=node.process_count,
                                network=dict(node.network),
                                status="OFFLINE",
                                last_heartbeat=node.last_heartbeat,
                                last_sequence=node.last_sequence,
                                total_packets=node.total_packets,
                                last_addr=node.last_addr,
                                last_packet_type=node.last_packet_type,
                                reason=node.reason,
                            )
                        )

        return timed_out_nodes

    def get_node(self, node_id: str) -> Optional[NodeState]:
        """Get state snapshot for a single node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return None
            return NodeState(
                node_id=node.node_id,
                cpu_percent=node.cpu_percent,
                memory_percent=node.memory_percent,
                process_count=node.process_count,
                network=dict(node.network),
                status=node.status,
                last_heartbeat=node.last_heartbeat,
                last_sequence=node.last_sequence,
                total_packets=node.total_packets,
                last_addr=node.last_addr,
                last_packet_type=node.last_packet_type,
                reason=node.reason,
            )

    def get_all_nodes(self) -> Dict[str, NodeState]:
        """Get snapshots of all tracked nodes."""
        with self._lock:
            return {
                nid: NodeState(
                    node_id=node.node_id,
                    cpu_percent=node.cpu_percent,
                    memory_percent=node.memory_percent,
                    process_count=node.process_count,
                    network=dict(node.network),
                    status=node.status,
                    last_heartbeat=node.last_heartbeat,
                    last_sequence=node.last_sequence,
                    total_packets=node.total_packets,
                    last_addr=node.last_addr,
                    last_packet_type=node.last_packet_type,
                    reason=node.reason,
                )
                for nid, node in sorted(self._nodes.items())
            }

    def get_counts(self) -> Tuple[int, int]:
        """Return (active_nodes_count, total_nodes_count)."""
        with self._lock:
            total = len(self._nodes)
            active = sum(1 for n in self._nodes.values() if n.status != "OFFLINE")
            return active, total

    def reset(self):
        """Reset all tracked nodes."""
        with self._lock:
            self._nodes.clear()
