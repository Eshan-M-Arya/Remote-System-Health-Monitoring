# Remote System Health Monitoring Using UDP

A distributed health-monitoring application built in Python where multiple remote/simulated server nodes periodically transmit system telemetry (CPU, memory, processes, network statistics) to a centralized monitoring server over **UDP** (User Datagram Protocol).

Designed and structured for a college-level distributed systems and networking project, emphasizing clear architecture, protocol comprehension, failure detection, priority handling, and experimental validation.

---

## 1. Introduction

In distributed infrastructure and cloud clusters, operators need real-time visibility into the health of hundreds or thousands of nodes. Utilizing heavy connection-oriented protocols (like TCP or HTTP polling) for high-frequency heartbeats introduces significant connection overhead, socket state retention, and head-of-line blocking.

This project implements a lightweight telemetry system over **UDP**, paired with an application-level priority queue on the central server. The monitoring server receives metrics, evaluates configurable warning and critical thresholds, detects node dropouts (unresponsive nodes), prioritizes critical alerts, tracks microsecond/millisecond packet latency, and renders a live terminal dashboard.

---

## 2. Objectives

The project accomplishes all key requirements:
- **UDP Health Agents**: Lightweight agents collecting CPU, RAM, process count, and network I/O using `psutil`.
- **Centralized Server**: Multi-threaded UDP receiver and worker architecture managing concurrent node states.
- **Configurable Thresholds**: Warning and Critical alerts defined in a centralized `config.json`.
- **Logical Priority for Critical Traffic**: Critical conditions trigger immediate alert packets processed via an internal `PriorityQueue`.
- **Heartbeat-Based Failure Detection**: Automatic transition of unresponsive nodes to `OFFLINE` status after a timeout window.
- **Latency Measurement**: Accurate packet transit and processing latency measurement using monotonic high-resolution timing.
- **Scalability Evaluation**: Empirical benchmarking with 1 to 100 concurrent nodes demonstrating throughput, latency scaling, and UDP packet behavior.

---

## 3. System Architecture

```text
+-----------------------+      +-----------------------+      +-----------------------+
|  Agent: NODE-01       |      |  Agent: NODE-02       |      |  Agent: NODE-N        |
|  - psutil telemetry   |      |  - psutil telemetry   |      |  - psutil telemetry   |
|  - UDP socket client  |      |  - UDP socket client  |      |  - UDP socket client  |
+-----------------------+      +-----------------------+      +-----------------------+
            |                              |                              |
            | UDP Datagrams (JSON)         | UDP Datagrams (JSON)         | UDP Datagrams (JSON)
            +------------------------------+------------------------------+
                                           |
                                           v
               +=======================================================+
               |             CENTRAL MONITORING SERVER                 |
               +=======================================================+
               |  1. UDP Receiver Thread:                              |
               |     - Listens on 127.0.0.1:5000                       |
               |     - Validates JSON datagrams                        |
               |     - Assigns logical priority (CRITICAL > HEALTH)    |
               +-------------------------------------------------------+
                                           |
                                           v
               +-------------------------------------------------------+
               |  2. Priority Queue (PriorityQueue):                   |
               |     - Priority 0: CRITICAL alerts                     |
               |     - Priority 1: WARNING alerts                      |
               |     - Priority 2: Standard HEALTH heartbeats          |
               +-------------------------------------------------------+
                                           |
                                           v
               +-------------------------------------------------------+
               |  3. Processing Worker Thread:                         |
               |     - Latency Tracker: (T_recv - T_send)              |
               |     - Alert Manager: Threshold evaluation             |
               |     - Node Manager: State persistence & metrics       |
               +-------------------------------------------------------+
                                           |
               +---------------------------+---------------------------+
               |                                                       |
               v                                                       v
+-------------------------------+               +-------------------------------+
|  4. Timeout Detector Thread   |               |  5. Terminal Dashboard Thread |
|  - Heartbeat > 5.0s -> OFFLINE|               |  - Live tabular node status   |
|  - Emits [FAILURE] alerts     |               |  - Recent alerts & latency    |
+-------------------------------+               +-------------------------------+
```

---

## 4. Key Networking Concepts & Why UDP?

1. **Why UDP for Periodic Health Monitoring?**
   - **Connectionless**: No TCP 3-way handshake (`SYN` / `SYN-ACK` / `ACK`) or connection teardown (`FIN` / `RST`). The server does not maintain expensive socket buffers per node.
   - **Low Overhead**: A UDP header is only **8 bytes**, compared to a minimum **20 bytes** for TCP.
   - **Stateless & Scalable**: A single UDP server port can effortlessly service hundreds or thousands of nodes.
   - **Acceptable Packet Loss**: Because health telemetry is sent periodically (e.g. every 1 second), losing an occasional packet is harmless; the very next packet provides fresh system state.

2. **Why UDP does NOT provide QoS or Priority:**
   - Standard UDP operates at Layer 4 (Transport Layer) with best-effort delivery. It does not provide Quality of Service (QoS), delivery guarantees, or packet ordering.
   - **Our Priority Mechanism**: Logical prioritization is implemented at the **application layer** on the server. The receiver places incoming packets into a multi-tiered `PriorityQueue`, ensuring that `CRITICAL` alert packets are processed by worker threads ahead of normal periodic heartbeats.

---

## 5. Packet Design

All packets are serialized as UTF-8 encoded JSON over UDP datagrams.

### Standard Health Telemetry Packet (`HEALTH`)
```json
{
  "type": "HEALTH",
  "node_id": "NODE-01",
  "sequence": 42,
  "timestamp": 1774852930.123,
  "send_time_mono": 18452.784,
  "cpu_percent": 34.5,
  "memory_percent": 61.2,
  "process_count": 154,
  "network": {
    "bytes_sent": 1284920,
    "bytes_recv": 8492014
  }
}
```

### Critical Alert Packet (`CRITICAL`)
```json
{
  "type": "CRITICAL",
  "node_id": "NODE-03",
  "sequence": 43,
  "timestamp": 1774852930.456,
  "send_time_mono": 18453.117,
  "cpu_percent": 95.4,
  "memory_percent": 88.0,
  "process_count": 210,
  "network": {
    "bytes_sent": 1285000,
    "bytes_recv": 8492100
  },
  "reason": "CPU usage exceeded critical threshold: 95.4% >= 90.0%"
}
```

---

## 6. Project Structure

```text
remote-system-health-monitoring/
│
├── server/
│   ├── monitor_server.py      # UDP server, priority queue, and dashboard
│   ├── alert_manager.py       # Threshold evaluation & alert history
│   ├── node_manager.py        # Thread-safe node state & timeout detection
│   └── latency_tracker.py     # Latency statistics calculator
│
├── agents/
│   └── health_agent.py        # Metric collector & UDP reporting agent
│
├── experiments/
│   ├── latency_test.py        # Automated latency benchmark
│   ├── failure_test.py        # Automated node failure verification
│   ├── scalability_test.py    # Scalability suite (1 to 100 nodes)
│   ├── latency_results.csv    # Measured latency data
│   └── scalability_results.csv# Measured scalability data
│
├── config/
│   └── config.json            # Centralized threshold & network configuration
│
├── logs/                      # Runtime logs directory
│
├── tests/
│   ├── test_protocol.py       # Packet serialization and validation tests
│   ├── test_alert_manager.py  # Alert threshold and recovery tests
│   ├── test_node_manager.py   # State tracking and timeout tests
│   └── test_e2e.py            # End-to-end integration tests
│
├── requirements.txt           # Minimal dependencies (psutil)
├── .gitignore                 # Standard Python gitignore
└── README.md                  # Comprehensive documentation
```

---

## 7. Installation & Setup

### Requirements
- Python 3.8 or newer
- Operating System: Windows, Linux, or macOS

### Step 1: Create and Activate Virtual Environment

**On Windows (Command Prompt / PowerShell):**
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**On Linux / macOS / WSL:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 8. How to Run

### Step 1: Start Central Monitoring Server
In Terminal 1:
```bash
# Using virtualenv python:
python server/monitor_server.py
```
*Optional Flags:*
- `--port 5000`: Override default UDP port.
- `--timeout 5.0`: Change node failure timeout window (seconds).
- `--headless`: Run without clearing and updating stdout (useful for background scripts).

### Step 2: Start Health Agents
Open additional terminal windows to start agents:

**Normal Agent (reports real system stats every 1 second):**
```bash
python agents/health_agent.py --node-id NODE-01
```

**Simulate Warning Condition (CPU = 85%):**
```bash
python agents/health_agent.py --node-id NODE-02 --simulate-cpu 85.0
```

**Simulate Critical Condition (Immediate Alert + CPU = 96%):**
```bash
python agents/health_agent.py --node-id NODE-03 --simulate-cpu 96.0
```

**Simulate Node Failure (Transmits 5 packets and then stops):**
```bash
python agents/health_agent.py --node-id NODE-04 --simulate-failure
```

---

## 9. Terminal Dashboard Output

```text
============================================================
             REMOTE SYSTEM HEALTH MONITOR (UDP)
============================================================
Server: 127.0.0.1:5000 | Time: 2026-10-03 06:49:30

NODE         CPU        MEMORY     PROCESSES    STATUS    
------------------------------------------------------------
NODE-01       3.4%       9.7%      36           ONLINE    
NODE-02      85.0%       9.7%      36           WARNING   
NODE-03      96.0%       9.7%      36           CRITICAL  
NODE-04        --         --       --           OFFLINE   
------------------------------------------------------------

RECENT ALERTS
  [FAILURE] NODE-04 - Node stopped responding (no heartbeat for >5.0s) (06:49:28)
  [CRITICAL] NODE-03 - CPU exceeded critical threshold: 96.0% >= 90.0% (06:49:24)
  [WARNING]  NODE-02 - CPU exceeded warning threshold: 85.0% >= 80.0% (06:49:21)

LATENCY STATISTICS
  Packets: 45 | Avg: 0.18 ms | Min: 0.08 ms | Max: 0.95 ms | Last: 0.12 ms

ACTIVE NODES: 3/4 | TOTAL PACKETS: 45
============================================================
```

---

## 10. Automated Tests & Verification

The project includes unit and end-to-end tests covering all protocol, threshold, priority, and timeout functionality.

Run the test suite:
```bash
python -m unittest discover tests
```

Output:
```text
Ran 19 tests in 6.419s

OK
```

---

## 11. Experimental Results & Benchmarks

All metrics below were **empirically measured** on the system by executing the benchmark harnesses.

### Experiment 1: Packet & Alert Latency (`experiments/latency_test.py`)
Measures the latency between an agent sending a packet and the server receiving and queuing it for processing:

```bash
python experiments/latency_test.py --packets 100 --interval 0.01
```

**Empirical Measurements:**
| Metric | Measured Value |
| :--- | :--- |
| **Total Packets Sent** | 100 |
| **Packets Processed** | 100 (100% Delivery) |
| **Minimum Latency** | **0.070 ms** |
| **Average Latency** | **0.140 ms** |
| **Maximum Latency** | **0.870 ms** |

*Output CSV saved at `experiments/latency_results.csv`.*

---

### Experiment 2: Node Failure Detection (`experiments/failure_test.py`)
Starts `NODE-HEALTHY` (continuous) and `NODE-FAILING` (stops transmitting after 2.5 seconds), with a configured server timeout of 2.5 seconds:

```bash
python experiments/failure_test.py --timeout 2.5
```

**Observed Timeline:**
- `[+0.00s]`: Both nodes commence transmission.
- `[+2.50s]`: `NODE-FAILING` halts packet transmission.
- `[+5.41s]`: Server timeout detector triggers (2.91s after last packet).
- `[+5.41s]`: Node status transitions to `OFFLINE`.
- `[+5.41s]`: `[FAILURE] NODE-FAILING - Node stopped responding` alert is emitted.
- `NODE-HEALTHY` continues operating as `ONLINE` unaffected.

---

### Experiment 3: Scalability Evaluation (`experiments/scalability_test.py`)
Evaluates system throughput, latency, loss rate, and server memory consumption across **1, 5, 10, 25, 50, and 100 concurrent nodes**:

```bash
python experiments/scalability_test.py --nodes 1 5 10 25 50 100 --packets 10 --interval 0.05
```

**Empirical Scalability Results Table:**
| Node Count | Total Sent | Total Received | Loss Rate (%) | Throughput (pkts/sec) | Avg Latency (ms) | Server Memory (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 10 | 10 | **0.0%** | 9.9 | 0.30 | 15.6 |
| **5** | 50 | 50 | **0.0%** | 49.1 | 0.23 | 15.8 |
| **10** | 100 | 100 | **0.0%** | 88.0 | 0.28 | 16.2 |
| **25** | 250 | 250 | **0.0%** | 194.2 | 0.45 | 17.1 |
| **50** | 500 | 500 | **0.0%** | 252.6 | 3.34 | 18.8 |
| **100** | 1000 | 851 | **14.9%** | 211.2 | 329.62 | 21.9 |

*Output CSV saved at `experiments/scalability_results.csv`.*

### Analysis of Scalability Results:
1. **Low to Medium Concurrency (1 - 50 nodes)**:
   - Packet delivery is **100% (0.0% loss)** with sub-millisecond average latency (< 3.5 ms).
   - Throughput scales linearly up to **252.6 packets/sec**.
   - Server memory remains virtually constant (~16 - 19 MB), highlighting the efficiency of stateless UDP sockets.
2. **High Concurrency Burst (100 nodes)**:
   - When 100 nodes simultaneously burst datagrams at 50ms intervals, the operating system's UDP socket receive buffer fills faster than single-threaded socket read loops can drain it.
   - Consequently, **14.9% packet drop** occurred. This accurately reflects real-world UDP behavior: when packet bursts exceed socket buffer capacity, the operating system drops packets silently without backpressure.

---

## 12. Realistic Limitations

1. **UDP Packet Dropping**: Under network congestion or buffer saturation, UDP datagrams are dropped without acknowledgement or automatic retransmission.
2. **No Built-in Encryption / Authentication**: Datagrams are transmitted in cleartext JSON. In a production environment, packets should be secured via DTLS (Datagram Transport Layer Security) or HMAC signing.
3. **Local Clock vs Distributed Clocks**: On a single machine, high-resolution monotonic clocks (`time.perf_counter()`) provide microsecond precision for latency. In distributed networks, latency measurement requires NTP or PTP clock synchronization.

---

## 13. Future Improvements

- **DTLS / HMAC Security**: Prevent IP spoofing and unauthorized telemetry injection.
- **Web Dashboard**: Modern WebSocket/React browser dashboard replacing the terminal UI.
- **Persistent Storage**: Integration with a time-series database (e.g. InfluxDB or TimescaleDB).
- **Application-Level ACK for Critical Alerts**: Implement stop-and-wait or selective repeat retransmissions strictly for `CRITICAL` alerts while keeping standard `HEALTH` telemetry lightweight.

---

## 14. Viva / Defense Preparation Guide

### Q1: Why did you choose UDP instead of TCP for health monitoring?
> **Answer**: TCP is connection-oriented and requires a three-way handshake (`SYN`, `SYN-ACK`, `ACK`), connection state maintenance per client, and retransmission mechanisms. For high-frequency heartbeat telemetry, maintaining thousands of persistent TCP connections imposes significant memory overhead and file descriptor exhaustion. Furthermore, TCP's head-of-line blocking is undesirable for monitoring: if packet #1 is lost, TCP stalls packet #2 waiting for retransmission, even though packet #2 has newer, more relevant health data. With UDP, heartbeats are connectionless and lightweight; if one heartbeat is dropped, the subsequent one arrives in 1 second anyway.

### Q2: How is critical traffic prioritized if UDP does not support Quality of Service (QoS)?
> **Answer**: Standard UDP operates at the transport layer without built-in packet priority or QoS guarantees. To solve this, our project implements **application-layer priority queuing**:
> 1. The agent detects critical threshold breaches immediately and dispatches an urgent `CRITICAL` packet rather than waiting for the next periodic interval.
> 2. The server's socket receiver places datagrams into an internal `PriorityQueue` where `CRITICAL` packets have priority index 0 and `HEALTH` packets have priority index 2.
> 3. The server's worker threads dequeue and process `CRITICAL` alerts before processing standard heartbeats.

### Q3: How does the system detect that a node has crashed?
> **Answer**: The server's `NodeManager` maintains a `last_heartbeat` timestamp for every node. A dedicated background thread executes every 500ms and compares `current_time - last_heartbeat` against the configured timeout threshold (default 5.0 seconds). If a node exceeds this threshold, its status transitions from `ONLINE` to `OFFLINE`, and a `[FAILURE]` alert is logged.

### Q4: Why did packet loss occur at 100 concurrent nodes during scalability testing?
> **Answer**: When 100 node threads burst packets simultaneously on the loopback interface, the packet arrival rate briefly exceeded the OS kernel socket receive buffer drain rate. Since UDP does not implement flow control or backpressure, the kernel drops incoming datagrams once the receive buffer overflows. This demonstrates why production UDP architectures increase socket buffer sizes (`SO_RCVBUF`) or scale receiver worker threads.
