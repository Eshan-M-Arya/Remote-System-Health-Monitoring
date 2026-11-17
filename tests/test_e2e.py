"""
End-to-End integration tests for UDP Server and Health Agent.
Tests live UDP network communication, priority handling, failure detection, and latency tracking.
"""

import os
import sys
import threading
import time
import unittest

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents.health_agent import HealthAgent
from server.monitor_server import MonitorServer


class TestEndToEnd(unittest.TestCase):

    def setUp(self):
        self.port = 5088
        self.server = MonitorServer(
            host="127.0.0.1",
            port=self.port,
            node_timeout=1.5,
            cpu_warning=70.0,
            cpu_critical=85.0,
            headless=True,
        )
        self.server.start()
        time.sleep(0.15)

    def tearDown(self):
        self.server.stop()

    def test_single_agent_communication(self):
        agent = HealthAgent(
            node_id="NODE-TEST-01",
            server_host="127.0.0.1",
            server_port=self.port,
            interval=0.1,
            simulate_cpu=35.0,
            simulate_memory=45.0,
        )
        agent.run(max_packets=3, verbose=False)
        time.sleep(0.3)

        node = self.server.node_manager.get_node("NODE-TEST-01")
        self.assertIsNotNone(node)
        self.assertEqual(node.node_id, "NODE-TEST-01")
        self.assertEqual(node.cpu_percent, 35.0)
        self.assertEqual(node.memory_percent, 45.0)
        self.assertEqual(node.status, "ONLINE")
        self.assertEqual(node.total_packets, 3)

        stats = self.server.latency_tracker.get_stats()
        self.assertGreaterEqual(stats.count, 3)
        self.assertGreaterEqual(stats.avg_ms, 0.0)

    def test_multiple_agents_concurrent(self):
        agents = []
        threads = []
        node_ids = [f"MULTI-{i}" for i in range(5)]

        for nid in node_ids:
            ag = HealthAgent(
                node_id=nid,
                server_host="127.0.0.1",
                server_port=self.port,
                interval=0.1,
                simulate_cpu=25.0,
                simulate_memory=30.0,
            )
            agents.append(ag)
            t = threading.Thread(target=ag.run, kwargs={"max_packets": 3, "verbose": False})
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        time.sleep(0.4)
        nodes = self.server.node_manager.get_all_nodes()
        for nid in node_ids:
            self.assertIn(nid, nodes)
            self.assertEqual(nodes[nid].status, "ONLINE")

    def test_threshold_alerts(self):
        # Warning agent
        ag_warn = HealthAgent(
            node_id="NODE-WARN",
            server_host="127.0.0.1",
            server_port=self.port,
            interval=0.1,
            simulate_cpu=75.0,  # Warning is >= 70
        )
        ag_warn.run(max_packets=1, verbose=False)

        # Critical agent
        ag_crit = HealthAgent(
            node_id="NODE-CRIT",
            server_host="127.0.0.1",
            server_port=self.port,
            interval=0.1,
            simulate_cpu=92.0,  # Critical is >= 85
        )
        ag_crit.run(max_packets=1, verbose=False)

        time.sleep(0.4)
        warn_node = self.server.node_manager.get_node("NODE-WARN")
        crit_node = self.server.node_manager.get_node("NODE-CRIT")

        self.assertIsNotNone(warn_node)
        self.assertEqual(warn_node.status, "WARNING")

        self.assertIsNotNone(crit_node)
        self.assertEqual(crit_node.status, "CRITICAL")

        alerts = self.server.alert_manager.get_recent_alerts(limit=10)
        severities = [a.severity for a in alerts]
        self.assertIn("WARNING", severities)
        self.assertIn("CRITICAL", severities)

    def test_immediate_critical_alert(self):
        agent = HealthAgent(
            node_id="NODE-IMMEDIATE",
            server_host="127.0.0.1",
            server_port=self.port,
            interval=5.0,  # Long interval
        )
        # Send immediate critical alert bypassing normal interval
        agent.send_critical_alert("Emergency CPU overload")
        time.sleep(0.3)

        node = self.server.node_manager.get_node("NODE-IMMEDIATE")
        self.assertIsNotNone(node)
        self.assertEqual(node.status, "CRITICAL")
        self.assertEqual(node.last_packet_type, "CRITICAL")
        agent.close()

    def test_node_failure_detection(self):
        agent = HealthAgent(
            node_id="NODE-DIE",
            server_host="127.0.0.1",
            server_port=self.port,
            interval=0.1,
        )
        agent.run(max_packets=2, verbose=False)
        time.sleep(0.2)

        # Right after packets, should be ONLINE
        node = self.server.node_manager.get_node("NODE-DIE")
        self.assertEqual(node.status, "ONLINE")

        # Wait past node_timeout (1.5s)
        time.sleep(1.8)
        node_after = self.server.node_manager.get_node("NODE-DIE")
        self.assertEqual(node_after.status, "OFFLINE")

        # Verify failure alert was logged
        alerts = self.server.alert_manager.get_recent_alerts(limit=5)
        failure_alerts = [a for a in alerts if a.severity == "FAILURE" and a.node_id == "NODE-DIE"]
        self.assertGreaterEqual(len(failure_alerts), 1)


if __name__ == "__main__":
    unittest.main()
