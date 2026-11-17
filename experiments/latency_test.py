"""
Mininet Latency Experiment for Remote System Health Monitoring.

Uses the existing monitor_server.py and health_agent.py
inside real Mininet hosts.

h1 = monitoring server
h2 = telemetry agent
s1 = Open vSwitch
"""

import argparse
import csv
import os
import re
import signal
import subprocess
import sys
import time

from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

SERVER_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "server",
    "monitor_server.py",
)

AGENT_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "agents",
    "health_agent.py",
)


def run_latency_experiment(
    num_packets=100,
    packet_interval=0.01,
    host="10.0.0.1",
    port=5055,
    output_csv=None,
):
    print("=" * 65)
    print("       UDP HEALTH MONITOR — MININET LATENCY EXPERIMENT")
    print("=" * 65)
    print(f"Server: {host}:{port}")
    print(f"Packets: {num_packets}")
    print(f"Interval: {packet_interval * 1000:.2f} ms")
    print("-" * 65)

    if output_csv is None:
        output_csv = os.path.join(
            PROJECT_ROOT,
            "experiments",
            "latency_results.csv",
        )

    net = Mininet(
        switch=OVSBridge,
        link=TCLink,
    )

    h1 = net.addHost(
        "h1",
        ip="10.0.0.1/24",
    )

    h2 = net.addHost(
        "h2",
        ip="10.0.0.2/24",
    )

    s1 = net.addSwitch("s1")

    net.addLink(h1, s1)
    net.addLink(h2, s1)

    server_proc = None
    agent_proc = None

    try:
        net.start()

        print()
        print("=== MININET LATENCY TOPOLOGY ===")
        print("h1 = Server  10.0.0.1")
        print("h2 = Agent   10.0.0.2")
        print("s1 = OVS Switch")
        print("===============================")
        print()

        print("[*] Starting existing UDP Health Monitor Server...")

        server_proc = h1.popen(
            [
                "python3",
                "-u",
                SERVER_SCRIPT,
                "--host",
                host,
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        time.sleep(1.0)

        print("[*] Starting existing Health Agent on h2...")

        agent_proc = h2.popen(
            [
                "python3",
                "-u",
                AGENT_SCRIPT,
                "--node-id",
                "LATENCY-NODE",
                "--host",
                host,
                "--port",
                str(port),
                "--interval",
                str(packet_interval),
                "--count",
                str(num_packets),
                "--quiet",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(
            f"[*] Sending {num_packets} UDP telemetry packets "
            f"from h2 to h1..."
        )

        try:
            agent_output, _ = agent_proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            agent_proc.kill()
            agent_output, _ = agent_proc.communicate()

        print("[*] Agent transmission complete.")

        time.sleep(1.5)

        server_proc.send_signal(signal.SIGTERM)

        try:
            server_output, _ = server_proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
            server_output, _ = server_proc.communicate()

        if server_output is None:
            server_output = ""

        print()
        print("=" * 65)
        print("                  LATENCY TEST RESULTS")
        print("=" * 65)
        print(f"Total Packets Sent:     {num_packets}")

        latency_lines = re.findall(
            r"Packets:\s*(\d+)\s*\|\s*Avg:\s*([0-9.]+)\s*ms\s*\|\s*Min:\s*([0-9.]+)\s*ms\s*\|\s*Max:\s*([0-9.]+)\s*ms\s*\|\s*Last:\s*([0-9.]+)\s*ms",
            server_output,
        )

        if not latency_lines:
            print()
            print("Server output:")
            print(server_output)
            print("=" * 65)
            raise RuntimeError(
                "Could not read latency statistics from the Mininet server."
            )

        packets, avg_ms, min_ms, max_ms, last_ms = latency_lines[-1]

        print(f"Packets Processed:      {packets}")
        print(f"Minimum Latency:        {float(min_ms):.3f} ms")
        print(f"Maximum Latency:        {float(max_ms):.3f} ms")
        print(f"Average Latency:        {float(avg_ms):.3f} ms")
        print(f"Last Latency:           {float(last_ms):.3f} ms")
        print("=" * 65)

        latency_stats = [
            [
                "packets_processed",
                "minimum_ms",
                "maximum_ms",
                "average_ms",
                "last_ms",
            ],
            [
                int(packets),
                float(min_ms),
                float(max_ms),
                float(avg_ms),
                float(last_ms),
            ],
        ]

        os.makedirs(
            os.path.dirname(os.path.abspath(output_csv)),
            exist_ok=True,
        )

        with open(
            output_csv,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.writer(f)
            writer.writerows(latency_stats)

        print()
        print(f"[*] Results saved to: {output_csv}")

        return {
            "packets": int(packets),
            "min_ms": float(min_ms),
            "max_ms": float(max_ms),
            "avg_ms": float(avg_ms),
            "last_ms": float(last_ms),
        }

    finally:
        if agent_proc is not None:
            try:
                agent_proc.terminate()
            except Exception:
                pass

        if server_proc is not None:
            try:
                server_proc.terminate()
            except Exception:
                pass

        net.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Run Mininet UDP Latency Benchmark"
    )

    parser.add_argument(
        "--packets",
        type=int,
        default=100,
        help="Number of packets to send",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.01,
        help="Interval between packets in seconds",
    )

    parser.add_argument(
        "--host",
        default="10.0.0.1",
        help="Server IP address",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5055,
        help="Server UDP port",
    )

    parser.add_argument(
        "--csv",
        default=os.path.join(
            PROJECT_ROOT,
            "experiments",
            "latency_results.csv",
        ),
        help="CSV output file",
    )

    args = parser.parse_args()

    run_latency_experiment(
        num_packets=args.packets,
        packet_interval=args.interval,
        host=args.host,
        port=args.port,
        output_csv=args.csv,
    )


if __name__ == "__main__":
    setLogLevel("info")
    main()
