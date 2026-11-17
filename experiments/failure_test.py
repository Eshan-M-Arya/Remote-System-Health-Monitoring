import argparse
import os
import re
import time

from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_IP = "10.0.0.1"


def run_failure_experiment(timeout_sec=3.0, host=SERVER_IP, port=5056, stop_after=2.5):
    if os.geteuid() != 0:
        raise SystemExit("Run this experiment with sudo.")

    net = Mininet(switch=OVSBridge, link=TCLink)
    h1 = net.addHost("h1", ip=f"{SERVER_IP}/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    s1 = net.addSwitch("s1")

    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s1)

    server = healthy = failing = None

    print("=" * 70)
    print("       UDP HEALTH MONITOR — MININET FAILURE EXPERIMENT")
    print("=" * 70)
    print(f"Server: {host}:{port}")
    print(f"Timeout: {timeout_sec:.1f}s")
    print(f"Failing node stops after: {stop_after:.1f}s")
    print("-" * 70)

    try:
        net.start()

        server = h1.popen(
            [
                "python3",
                "-u",
                os.path.join(
                    PROJECT_ROOT, "server", "monitor_server.py"
                ),
                "--host",
                host,
                "--port",
                str(port),
                "--timeout",
                str(timeout_sec),
            ],
            stdout=open("/tmp/failure_server.log", "w"),
            stderr=open("/tmp/failure_server.err", "w"),
        )

        time.sleep(0.5)

        healthy = h2.popen(
            [
                "python3",
                "-u",
                os.path.join(
                    PROJECT_ROOT, "agents", "health_agent.py"
                ),
                "--node-id",
                "NODE-HEALTHY",
                "--host",
                host,
                "--port",
                str(port),
                "--interval",
                "0.8",
                "--quiet",
            ]
        )

        failing = h3.popen(
            [
                "python3",
                "-u",
                os.path.join(
                    PROJECT_ROOT, "agents", "health_agent.py"
                ),
                "--node-id",
                "NODE-FAILING",
                "--host",
                host,
                "--port",
                str(port),
                "--interval",
                "0.8",
                "--stop-after",
                str(stop_after),
                "--quiet",
            ]
        )

        start = time.time()
        detected = False
        detection_delay = None
        deadline = start + stop_after + timeout_sec + 3.0

        print("[+0.00s] Started NODE-HEALTHY on h2")
        print("[+0.00s] Started NODE-FAILING on h3")

        while time.time() < deadline:
            time.sleep(0.25)

            output = h1.cmd(
                "cat /tmp/failure_server.log"
            )

            if "NODE-FAILING" in output and "OFFLINE" in output:
                detected = True
                detection_delay = (
                    time.time() - (start + stop_after)
                )

                print(
                    f"[+{time.time() - start:.2f}s] "
                    "[SUCCESS] NODE-FAILING detected OFFLINE"
                )

                print(
                    f"Detection delay: "
                    f"{detection_delay:.2f}s"
                )

                break

        time.sleep(0.5)

        output = h1.cmd(
            "cat /tmp/failure_server.log"
        )

        print("-" * 70)
        print("SERVER OUTPUT")
        print("-" * 70)
        print(output[-5000:])

        failure_alert = bool(
            re.search(
                r"FAILURE.*NODE-FAILING|NODE-FAILING.*FAILURE",
                output,
                re.IGNORECASE,
            )
        )

        print("-" * 70)

        if detected and failure_alert:
            print(
                "EXPERIMENT PASSED: "
                "Node failure was detected and a FAILURE alert was recorded."
            )
        elif detected:
            print(
                "EXPERIMENT PASSED: "
                "Node failure was detected. "
                "FAILURE alert was not confirmed in captured output."
            )
        else:
            print(
                "EXPERIMENT FAILED: "
                "NODE-FAILING was not detected as OFFLINE."
            )

        print("=" * 70)

        return detected and failure_alert

    finally:
        for proc in (healthy, failing):
            if proc is not None and proc.poll() is None:
                proc.terminate()

        if server is not None and server.poll() is None:
            server.terminate()

        net.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Run Mininet node failure experiment"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
    )

    parser.add_argument(
        "--stop-after",
        type=float,
        default=2.5,
    )

    parser.add_argument(
        "--host",
        default=SERVER_IP,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5056,
    )

    args = parser.parse_args()

    run_failure_experiment(
        args.timeout,
        args.host,
        args.port,
        args.stop_after,
    )


if __name__ == "__main__":
    setLogLevel("info")
    main()
