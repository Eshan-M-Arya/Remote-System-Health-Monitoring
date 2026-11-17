#!/usr/bin/env python3

import argparse
import csv
import os
import re
import subprocess
import time

from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVER_SCRIPT = os.path.join(
    BASE_DIR,
    "server",
    "monitor_server.py"
)

AGENT_SCRIPT = os.path.join(
    BASE_DIR,
    "agents",
    "health_agent.py"
)


def parse_stats(output):
    pattern = (
        r"Packets:\s*(\d+)\s*\|\s*"
        r"Avg:\s*([\d.]+)\s*ms\s*\|\s*"
        r"Min:\s*([\d.]+)\s*ms\s*\|\s*"
        r"Max:\s*([\d.]+)\s*ms\s*\|\s*"
        r"Last:\s*([\d.]+)\s*ms"
    )

    matches = re.findall(pattern, output)

    if not matches:
        return None

    packets, avg, minimum, maximum, last = matches[-1]

    return {
        "packets": int(packets),
        "avg": float(avg),
        "min": float(minimum),
        "max": float(maximum),
        "last": float(last),
    }


def write_csv(filename, result):
    fields = [
        "nodes",
        "packets_sent",
        "packets_received",
        "loss_percent",
        "avg_latency_ms",
        "min_latency_ms",
        "max_latency_ms",
        "last_latency_ms",
        "throughput_packets_per_sec",
    ]

    exists = os.path.exists(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        if not exists:
            writer.writeheader()

        writer.writerow(result)


def run_tier(
    node_count,
    packets_per_node,
    interval,
    server_ip,
    port,
    csv_file,
):
    print(
        f"[*] Running tier with {node_count:3d} Mininet nodes...",
        end="",
        flush=True
    )

    net = Mininet(
        switch=OVSBridge,
        link=TCLink,
        controller=None
    )

    h1 = net.addHost(
        "h1",
        ip="10.0.0.1/24"
    )

    agent_hosts = []

    for i in range(node_count):
        host = net.addHost(
            f"h{i + 2}",
            ip=f"10.0.0.{i + 2}/24"
        )

        agent_hosts.append(host)

    s1 = net.addSwitch("s1")

    net.addLink(h1, s1)

    for host in agent_hosts:
        net.addLink(host, s1)

    net.start()

    print(" started")

    # Start the existing server inside h1.
    server_cmd = [
        "python3",
        "-u",
        SERVER_SCRIPT,
        "--host",
        server_ip,
        "--port",
        str(port),
        "--headless",
    ]

    server = h1.popen(
        server_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Give the server time to bind to UDP port.
    time.sleep(1)

    agents = []

    # Start the existing agents inside their Mininet hosts.
    for i, host in enumerate(agent_hosts):

        node_id = f"NODE-{i + 1:03d}"

        agent_cmd = [
            "python3",
            "-u",
            AGENT_SCRIPT,
            "--node-id",
            node_id,
            "--host",
            server_ip,
            "--port",
            str(port),
            "--interval",
            str(interval),
            "--count",
            str(packets_per_node),
            "--quiet",
        ]

        agent = host.popen(
            agent_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        agents.append(agent)

    # Wait for every agent to finish sending packets.
    for agent in agents:
        try:
            agent.wait(timeout=30)
        except subprocess.TimeoutExpired:
            agent.kill()
            agent.wait()

    # Allow the server to process the final packet.
    time.sleep(1)

    # Read everything the server has printed.
    try:
        server.terminate()
        server_output, _ = server.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server_output, _ = server.communicate()

    if isinstance(server_output, bytes):
        server_output = server_output.decode(
            errors="replace"
        )

    stats = parse_stats(server_output)

    total_sent = node_count * packets_per_node

    if stats is None:
        received = 0
        avg_latency = 0.0
        min_latency = 0.0
        max_latency = 0.0
        last_latency = 0.0
    else:
        received = stats["packets"]
        avg_latency = stats["avg"]
        min_latency = stats["min"]
        max_latency = stats["max"]
        last_latency = stats["last"]

    lost = max(
        0,
        total_sent - received
    )

    loss_percent = (
        (lost / total_sent) * 100
        if total_sent
        else 0.0
    )

    duration = max(
        interval * packets_per_node,
        0.1
    )

    throughput = received / duration

    result = {
        "nodes": node_count,
        "packets_sent": total_sent,
        "packets_received": received,
        "loss_percent": round(
            loss_percent,
            2
        ),
        "avg_latency_ms": round(
            avg_latency,
            3
        ),
        "min_latency_ms": round(
            min_latency,
            3
        ),
        "max_latency_ms": round(
            max_latency,
            3
        ),
        "last_latency_ms": round(
            last_latency,
            3
        ),
        "throughput_packets_per_sec": round(
            throughput,
            2
        ),
    }

    print(
        f"  {node_count:<8}"
        f"{total_sent:<10}"
        f"{received:<10}"
        f"{loss_percent:<11.1f}"
        f"{avg_latency:<15.3f}"
        f"{throughput:<15.2f}"
    )

    if received == 0:
        print()
        print("WARNING: Server received 0 packets.")
        print("SERVER OUTPUT:")
        print("-" * 70)

        if server_output.strip():
            print(server_output)
        else:
            print("<no server output>")

        print("-" * 70)

    if csv_file:
        write_csv(
            csv_file,
            result
        )

    net.stop()

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Mininet scalability experiment"
    )

    parser.add_argument(
        "--nodes",
        nargs="+",
        type=int,
        default=[
            1,
            5,
            10,
            25,
            50,
            100
        ],
    )

    parser.add_argument(
        "--packets",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
    )

    parser.add_argument(
        "--host",
        default="10.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5070,
    )

    parser.add_argument(
        "--csv",
        default=os.path.join(
            BASE_DIR,
            "experiments",
            "scalability_results.csv"
        ),
    )

    args = parser.parse_args()

    print("=" * 90)
    print(
        "          UDP HEALTH MONITOR — MININET SCALABILITY EXPERIMENT"
    )
    print("=" * 90)

    print(
        f"Testing Node Counts: {args.nodes}"
    )

    print(
        f"Packets Per Node:    {args.packets}"
    )

    print(
        f"Reporting Interval:  {args.interval}s"
    )

    print("-" * 90)

    print(
        f"{'Nodes':<8}"
        f"{'Sent':<10}"
        f"{'Recv':<10}"
        f"{'Loss %':<11}"
        f"{'Avg Latency':<15}"
        f"{'Throughput':<15}"
    )

    print("-" * 90)

    if os.path.exists(args.csv):
        os.remove(args.csv)

    for index, node_count in enumerate(args.nodes):

        port = args.port + index

        run_tier(
            node_count=node_count,
            packets_per_node=args.packets,
            interval=args.interval,
            server_ip=args.host,
            port=port,
            csv_file=args.csv,
        )

        time.sleep(1)

    print("-" * 90)
    print("Scalability experiment complete.")

    print(
        f"Results saved to: {os.path.abspath(args.csv)}"
    )


if __name__ == "__main__":
    setLogLevel("info")
    main()
