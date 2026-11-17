"""
Unit tests for telemetry packet structure, validation, and serialization.
"""

import json
import os
import sys
import unittest

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents.health_agent import HealthAgent


class TestProtocol(unittest.TestCase):

    def setUp(self):
        self.agent = HealthAgent(node_id="TEST-NODE", server_host="127.0.0.1", server_port=9999)

    def tearDown(self):
        self.agent.close()

    def test_packet_structure_and_fields(self):
        metrics = {
            "cpu_percent": 42.5,
            "memory_percent": 68.1,
            "process_count": 140,
            "network": {"bytes_sent": 5000, "bytes_recv": 12000},
        }
        packet = self.agent.build_packet(packet_type="HEALTH", metrics=metrics)

        self.assertEqual(packet["node_id"], "TEST-NODE")
        self.assertEqual(packet["type"], "HEALTH")
        self.assertEqual(packet["sequence"], 1)
        self.assertEqual(packet["cpu_percent"], 42.5)
        self.assertEqual(packet["memory_percent"], 68.1)
        self.assertEqual(packet["process_count"], 140)
        self.assertIn("timestamp", packet)
        self.assertIn("send_time_mono", packet)
        self.assertEqual(packet["network"]["bytes_sent"], 5000)

    def test_sequence_monotonic_increment(self):
        p1 = self.agent.build_packet("HEALTH")
        p2 = self.agent.build_packet("HEALTH")
        p3 = self.agent.build_packet("CRITICAL")

        self.assertEqual(p1["sequence"], 1)
        self.assertEqual(p2["sequence"], 2)
        self.assertEqual(p3["sequence"], 3)

    def test_json_serialization(self):
        packet = self.agent.build_packet("HEALTH")
        encoded = json.dumps(packet).encode("utf-8")
        decoded = json.loads(encoded.decode("utf-8"))

        self.assertEqual(decoded["node_id"], packet["node_id"])
        self.assertEqual(decoded["sequence"], packet["sequence"])
        self.assertEqual(decoded["type"], "HEALTH")

    def test_critical_packet_fields(self):
        packet = self.agent.build_packet("CRITICAL", reason="High memory usage")
        self.assertEqual(packet["type"], "CRITICAL")
        self.assertEqual(packet["reason"], "High memory usage")


if __name__ == "__main__":
    unittest.main()
