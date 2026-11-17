"""
Unit tests for NodeManager state tracking, updates, and timeout detection.
"""

import os
import sys
import time
import unittest

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.node_manager import NodeManager


class TestNodeManager(unittest.TestCase):

    def setUp(self):
        self.mgr = NodeManager()

    def test_node_addition_and_update(self):
        packet = {
            "node_id": "NODE-01",
            "cpu_percent": 45.0,
            "memory_percent": 55.0,
            "process_count": 130,
            "network": {"bytes_sent": 100, "bytes_recv": 200},
            "sequence": 1,
            "type": "HEALTH",
        }
        state, is_new = self.mgr.update_node("NODE-01", packet, addr=("127.0.0.1", 12345), evaluated_status="ONLINE")
        self.assertTrue(is_new)
        self.assertEqual(state.node_id, "NODE-01")
        self.assertEqual(state.cpu_percent, 45.0)
        self.assertEqual(state.memory_percent, 55.0)
        self.assertEqual(state.process_count, 130)
        self.assertEqual(state.total_packets, 1)

        # Second update
        packet["cpu_percent"] = 50.0
        state2, is_new2 = self.mgr.update_node("NODE-01", packet, addr=("127.0.0.1", 12345), evaluated_status="ONLINE")
        self.assertFalse(is_new2)
        self.assertEqual(state2.cpu_percent, 50.0)
        self.assertEqual(state2.total_packets, 2)

    def test_multiple_independent_nodes(self):
        for i in range(5):
            nid = f"NODE-{i}"
            pkt = {"node_id": nid, "cpu_percent": 10.0 * i, "memory_percent": 20.0, "process_count": 100, "sequence": 1}
            self.mgr.update_node(nid, pkt)

        nodes = self.mgr.get_all_nodes()
        self.assertEqual(len(nodes), 5)
        active, total = self.mgr.get_counts()
        self.assertEqual(active, 5)
        self.assertEqual(total, 5)

    def test_timeout_detection(self):
        pkt = {"node_id": "NODE-OLD", "cpu_percent": 20.0, "memory_percent": 20.0, "process_count": 100, "sequence": 1}
        self.mgr.update_node("NODE-OLD", pkt)

        # Fake old timestamp
        with self.mgr._lock:
            self.mgr._nodes["NODE-OLD"].last_heartbeat = time.time() - 10.0

        timed_out = self.mgr.check_timeouts(timeout_seconds=5.0)
        self.assertEqual(len(timed_out), 1)
        self.assertEqual(timed_out[0].node_id, "NODE-OLD")
        self.assertEqual(timed_out[0].status, "OFFLINE")

        # Check node state after timeout
        node = self.mgr.get_node("NODE-OLD")
        self.assertIsNotNone(node)
        self.assertEqual(node.status, "OFFLINE")

        active, total = self.mgr.get_counts()
        self.assertEqual(active, 0)
        self.assertEqual(total, 1)


if __name__ == "__main__":
    unittest.main()
