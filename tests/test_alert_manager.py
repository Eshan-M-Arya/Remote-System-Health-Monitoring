"""
Unit tests for AlertManager threshold evaluation, alert dispatching, and history tracking.
"""

import os
import sys
import unittest

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.alert_manager import AlertManager


class TestAlertManager(unittest.TestCase):

    def setUp(self):
        self.mgr = AlertManager(
            cpu_warning=80.0,
            cpu_critical=90.0,
            memory_warning=80.0,
            memory_critical=90.0,
        )

    def test_normal_health(self):
        packet = {"node_id": "NODE-01", "cpu_percent": 30.0, "memory_percent": 40.0, "type": "HEALTH"}
        status, alert = self.mgr.evaluate_packet(packet)
        self.assertEqual(status, "ONLINE")
        self.assertIsNone(alert)

    def test_cpu_warning_threshold(self):
        packet = {"node_id": "NODE-01", "cpu_percent": 82.5, "memory_percent": 40.0, "type": "HEALTH"}
        status, alert = self.mgr.evaluate_packet(packet)
        self.assertEqual(status, "WARNING")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "WARNING")
        self.assertIn("CPU exceeded warning threshold", alert.message)

    def test_cpu_critical_threshold(self):
        packet = {"node_id": "NODE-01", "cpu_percent": 94.2, "memory_percent": 40.0, "type": "HEALTH"}
        status, alert = self.mgr.evaluate_packet(packet)
        self.assertEqual(status, "CRITICAL")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "CRITICAL")
        self.assertIn("CPU exceeded critical threshold", alert.message)

    def test_memory_critical_threshold(self):
        packet = {"node_id": "NODE-01", "cpu_percent": 40.0, "memory_percent": 92.0, "type": "HEALTH"}
        status, alert = self.mgr.evaluate_packet(packet)
        self.assertEqual(status, "CRITICAL")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "CRITICAL")
        self.assertIn("Memory exceeded critical threshold", alert.message)

    def test_explicit_critical_packet(self):
        packet = {
            "node_id": "NODE-01",
            "type": "CRITICAL",
            "reason": "Process fault",
            "cpu_percent": 50.0,
            "memory_percent": 50.0,
        }
        status, alert = self.mgr.evaluate_packet(packet)
        self.assertEqual(status, "CRITICAL")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.message, "Process fault")

    def test_recovery_alert(self):
        # Trigger critical first
        p_crit = {"node_id": "NODE-01", "cpu_percent": 95.0, "memory_percent": 50.0, "type": "HEALTH"}
        self.mgr.evaluate_packet(p_crit)

        # Return to normal
        p_norm = {"node_id": "NODE-01", "cpu_percent": 30.0, "memory_percent": 40.0, "type": "HEALTH"}
        status, alert = self.mgr.evaluate_packet(p_norm)
        self.assertEqual(status, "ONLINE")
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "RECOVERY")

    def test_failure_recording(self):
        alert = self.mgr.record_failure("NODE-TIMEOUT", "Node stopped reporting")
        self.assertEqual(alert.severity, "FAILURE")
        self.assertEqual(alert.node_id, "NODE-TIMEOUT")
        recent = self.mgr.get_recent_alerts(limit=5)
        self.assertIn(alert, recent)


if __name__ == "__main__":
    unittest.main()
