# Remote System Health Monitoring — Antigravity Build Prompt

## Role

Act as a senior Python/networking engineer helping me build a **college-level distributed systems/networking project**.

I need to submit this project in a few days, so prioritize:

1. A fully working implementation.
2. Clear, understandable code.
3. Demonstration of every requirement.
4. Easy testing and reproducibility.
5. Good documentation for a college report and viva.

Do **not** over-engineer this into a production monitoring platform.

---

# 1. Project Title

**Remote System Health Monitoring Using UDP**

## Project Objective

Build a distributed health-monitoring application in which multiple simulated/remote server nodes periodically send system-health information to a centralized monitoring server using **UDP**.

The monitoring server must:

- Receive health reports from multiple nodes.
- Track CPU, memory, process, and network information.
- Detect warning/critical conditions using configurable thresholds.
- Detect nodes that stop reporting.
- Handle critical monitoring traffic with higher priority.
- Measure alert/packet latency.
- Support experiments demonstrating scalability.

---

# 2. Required Features

The implementation must cover all of the following requirements.

### A. UDP Health-Reporting Agents

Create an agent program representing a remote server/node.

Each agent should periodically collect and transmit:

- Node ID
- Timestamp
- CPU utilization
- Memory utilization
- Process count
- Network statistics
- Message/packet type
- Sequence number if useful

Use Python's standard `socket` library with UDP.

Use `psutil` for system statistics.

Example information:

```text
NODE-01
CPU: 34%
Memory: 62%
Processes: 154
Network: ...
Timestamp: ...
```

---

### B. Centralized Monitoring Server

Create a central UDP monitoring server that:

- Listens for UDP packets.
- Parses incoming health reports.
- Maintains the latest state of every node.
- Displays node status.
- Records timestamps.
- Calculates packet/alert latency.
- Detects warning and critical conditions.
- Detects nodes that stop reporting.

The server should be able to handle multiple agents concurrently.

Prefer a simple, robust architecture such as a UDP receiver plus separate monitoring/state-management logic.

---

### C. Alert Thresholds

Make thresholds configurable rather than hard-coded throughout the code.

Suggested defaults:

```text
CPU:
  WARNING  >= 80%
  CRITICAL >= 90%

Memory:
  WARNING  >= 80%
  CRITICAL >= 90%
```

Also allow node failure detection based on a configurable timeout.

For example:

```text
If no health report is received for 5 seconds:
    mark node as OFFLINE
```

The exact values should be configurable from a central configuration file or constants section.

---

### D. Critical Monitoring Traffic

The project specification explicitly requires:

> Prioritize critical monitoring traffic.

Implement this clearly.

Normal health reports should be sent periodically.

If an agent detects a critical condition, it should immediately send a separate critical alert packet rather than waiting for the next normal reporting interval.

Use explicit message types such as:

```text
HEALTH
WARNING
CRITICAL
```

The monitoring server should process `CRITICAL` messages with higher logical priority.

If practical, implement separate handling/queues for normal and critical messages so the priority mechanism is demonstrable.

Do NOT falsely claim that UDP itself provides priority or QoS. Explain that the application implements logical priority at the monitoring layer.

---

### E. Simulated Node Failures

The system must support demonstration of node failure.

Provide a simple way to simulate a node stopping transmission.

For example:

```text
python health_agent.py --node-id NODE-03 --simulate-failure
```

or allow the agent to stop after a configurable amount of time.

The monitoring server should eventually display something like:

```text
[FAILURE] NODE-03 is offline
```

The timeout and failure-detection logic must be measurable and documented.

---

### F. Alert / Packet Latency

Measure the time between:

1. Agent sending a packet/critical alert.
2. Monitoring server receiving and processing it.

Use timestamps carefully.

Where possible, use a monotonic local measurement for latency experiments rather than relying only on wall-clock timestamps.

Record:

- Minimum latency
- Maximum latency
- Average latency
- Number of packets measured

Example:

```text
Latency Statistics
------------------
Packets: 100
Average: 2.4 ms
Minimum: 1.1 ms
Maximum: 8.7 ms
```

Do not invent experimental results. Generate results by actually running the system.

---

### G. Scalability Evaluation

The project must include a scalability experiment.

Allow multiple simulated nodes to run simultaneously on the same machine.

Test at least several node counts, for example:

```text
1
5
10
25
50
100
```

Use configurable node IDs and ports/behavior as necessary.

Measure useful metrics such as:

- Packets received per second
- Average latency
- Packet loss, if measurable
- Server processing time
- Server CPU/memory usage if practical

Produce data that can later be plotted.

Do not fabricate numbers.

---

# 3. Technology Requirements

Use:

- Python 3
- UDP sockets via `socket`
- `psutil`
- JSON for packet serialization
- `threading`, `queue`, or another simple standard-library mechanism where useful
- `time` / `datetime` for timing

Keep dependencies minimal.

Create:

```text
requirements.txt
```

with the required third-party packages.

Prefer cross-platform code because I am developing on Windows.

---

# 4. Suggested Project Structure

Create a clean structure similar to:

```text
remote-health-monitor/
│
├── server/
│   ├── monitor_server.py
│   ├── alert_manager.py
│   └── node_manager.py
│
├── agents/
│   └── health_agent.py
│
├── experiments/
│   ├── latency_test.py
│   ├── scalability_test.py
│   └── failure_test.py
│
├── config/
│   └── config.json
│
├── logs/
│
├── tests/
│
├── requirements.txt
├── README.md
└── .gitignore
```

You may adjust the structure if there is a technically better simple design, but keep it understandable for a second-year college student.

---

# 5. Packet Design

Use JSON packets over UDP.

Example normal health packet:

```json
{
  "type": "HEALTH",
  "node_id": "NODE-01",
  "sequence": 42,
  "timestamp": 1234567890.123,
  "cpu_percent": 37.5,
  "memory_percent": 61.2,
  "process_count": 153,
  "network": {
    "bytes_sent": 123456,
    "bytes_recv": 654321
  }
}
```

Critical alert example:

```json
{
  "type": "CRITICAL",
  "node_id": "NODE-01",
  "sequence": 43,
  "timestamp": 1234567890.456,
  "reason": "CPU usage exceeded critical threshold",
  "cpu_percent": 95.4
}
```

Validate incoming packets and handle malformed packets gracefully.

---

# 6. Monitoring Dashboard

Create a simple terminal dashboard.

It should show something approximately like:

```text
============================================================
             REMOTE SYSTEM HEALTH MONITOR
============================================================

NODE       CPU       MEMORY     PROCESSES     STATUS
------------------------------------------------------------
NODE-01    32%       61%       142            ONLINE
NODE-02    87%       73%       189            WARNING
NODE-03    95%       91%       211            CRITICAL
NODE-04    41%       52%       133            ONLINE
NODE-05     --        --         --            OFFLINE
------------------------------------------------------------

RECENT ALERTS
[CRITICAL] NODE-03 CPU = 95%
[WARNING]  NODE-02 CPU = 87%
[FAILURE]  NODE-05 stopped responding

LATENCY
Average: 3.2 ms

ACTIVE NODES: 4/5
============================================================
```

A sophisticated GUI is **not required**.

A clean terminal dashboard is sufficient unless there is a strong reason to add a lightweight web UI.

Do not spend project time on visual polish before the networking functionality is complete.

---

# 7. Important Networking Concepts

The implementation and README should clearly explain:

- What UDP is.
- Why UDP is appropriate for periodic monitoring traffic.
- UDP's lack of connection establishment.
- UDP's lack of built-in delivery guarantees.
- Why occasional health-packet loss can be acceptable.
- Why critical alerts require special handling/retransmission or application-level logic if reliability is needed.
- Client/agent and centralized-server architecture.
- Failure detection using heartbeats/health reports.
- Monitoring latency.
- Scalability considerations.

Do not incorrectly claim that UDP guarantees delivery, ordering, or priority.

---

# 8. Failure Handling

Handle at least:

- Invalid JSON
- Malformed packets
- Unknown node IDs
- UDP receive errors
- Agent shutdown
- Node timeout
- Duplicate sequence numbers if applicable
- Missing packets
- Unexpected values

The server should not crash because one malformed UDP packet arrives.

---

# 9. Testing

Create simple tests or scripts demonstrating:

### Test 1 — Basic communication

```text
1 agent → 1 monitoring server
```

Verify that health reports arrive.

### Test 2 — Multiple nodes

```text
5+ agents → 1 monitoring server
```

Verify that all nodes are tracked independently.

### Test 3 — Threshold alert

Cause or simulate high CPU/memory usage and verify warning/critical alerts.

If reliably generating real high CPU usage is difficult, provide a controlled simulation mode while clearly labeling it as simulated.

### Test 4 — Node failure

Stop an agent and verify that the server detects the node after the configured timeout.

### Test 5 — Critical traffic

Trigger a critical condition and demonstrate that the critical alert is sent immediately and processed with priority.

### Test 6 — Latency

Collect multiple latency measurements.

### Test 7 — Scalability

Run multiple simulated nodes and collect measurements.

---

# 10. Documentation

Create a strong `README.md` containing:

## 1. Introduction

What the project does.

## 2. Objectives

Map directly to the project requirements.

## 3. Architecture

Explain:

```text
Multiple Agents
       |
       | UDP
       ↓
Central Monitoring Server
       |
       ├── Node State
       ├── Alert Manager
       ├── Failure Detector
       └── Statistics
```

## 4. Technologies

Explain Python, UDP, sockets, psutil, JSON.

## 5. Installation

Give exact commands.

Example:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 6. Running the Server

Give exact command.

## 7. Running Agents

Give exact commands for multiple agents.

## 8. Testing

Explain each experiment.

## 9. Results

Provide tables/placeholders for actual measured results.

## 10. Limitations

Mention realistic limitations such as UDP packet loss and local-machine simulation.

## 11. Future Improvements

Examples:

- Persistent database
- Web dashboard
- Authentication/encryption
- Real remote machines
- Prometheus/Grafana integration
- More sophisticated alerting

---

# 11. Development Strategy

Do NOT build everything at once.

Implement incrementally in this order:

### Milestone 1

One UDP agent → one monitoring server.

Get this completely working first.

### Milestone 2

Add CPU, memory, process, and network statistics.

### Milestone 3

Add multiple agents.

### Milestone 4

Add thresholds and alerts.

### Milestone 5

Add node failure detection.

### Milestone 6

Add critical-message priority.

### Milestone 7

Add latency measurement.

### Milestone 8

Add scalability experiment.

### Milestone 9

Add tests, documentation, and final cleanup.

After each milestone, verify that the existing functionality still works.

---

# 12. Code Quality Requirements

Write code that a college student can understand and explain in a viva.

Use:

- Clear variable names.
- Functions with single responsibilities.
- Short useful comments.
- Type hints where they improve readability.
- Basic exception handling.
- No unnecessary frameworks.
- No unnecessary dependencies.

Avoid:

- Massive single-file implementations.
- Overengineering.
- Complex design patterns that aren't needed.
- Docker/Kubernetes unless specifically required.
- Cloud deployment.
- Authentication systems unless time permits after the core project works.
- GUI development before the core networking system is finished.

---

# 13. Very Important: Do Not Fake Results

The final project should distinguish between:

### Actual system measurements

Things measured by running the program.

### Simulated values

Values intentionally generated for demonstration.

Never present simulated results as real experimental measurements.

---

# 14. Antigravity Working Rules

Before making major architectural decisions, inspect the current project files.

If the repository is empty, initialize the project according to the structure above.

Build the project incrementally.

After implementing each milestone:

1. Run the code.
2. Check for errors.
3. Fix the errors.
4. Verify the functionality.
5. Update the README.
6. Tell me what was implemented and how to test it.

Do not simply generate code without verifying that it runs.

Keep the implementation compatible with Windows.

When a command needs to be run, give me the exact command.

When something fails, explain the cause briefly and fix it rather than hiding the error.

---

# 15. Final Deliverable

At the end, the repository should contain a working project that demonstrates all of these requirements:

- [ ] UDP health-reporting agents
- [ ] CPU statistics
- [ ] Memory statistics
- [ ] Process statistics
- [ ] Network statistics
- [ ] Centralized monitoring server
- [ ] Multiple simulated nodes
- [ ] Configurable alert thresholds
- [ ] Warning alerts
- [ ] Critical alerts
- [ ] Critical traffic prioritization
- [ ] Simulated node failures
- [ ] Failure detection
- [ ] Alert/packet latency measurement
- [ ] Scalability experiment
- [ ] Terminal monitoring dashboard
- [ ] Tests
- [ ] README documentation
- [ ] requirements.txt
- [ ] Clean project structure

---

# 16. Start Here

Do NOT immediately implement the entire project.

Start with **Milestone 1 only**:

> Build a minimal UDP monitoring server and a single health-reporting agent.

The first successful demonstration should be:

```text
health_agent.py
      |
      | UDP JSON packet
      ↓
monitor_server.py
      |
      ↓
Terminal output showing:
Node ID
CPU
Memory
Process count
Timestamp
```

Once this works, stop and explain:

1. What files were created.
2. How UDP communication works in this implementation.
3. How to run the server.
4. How to run the agent.
5. What output I should expect.
6. What we will implement in Milestone 2.

Do not proceed to later milestones until Milestone 1 is working.
