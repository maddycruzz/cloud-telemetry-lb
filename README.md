# Cloud Telemetry & Adaptive Load Balancer

An autonomous, self-healing cloud infrastructure simulator with metric-aware load balancing, anomaly detection, debounced alerting, and a minimal pastel command center.

---

## Architecture

```
                  [ Incoming HTTP Traffic ]
                              |
                              v
             [ Adaptive Load Balancer :8000 ]
              (Metric-Aware Reverse Proxy)
                     /                \
        [Failover]  /                  \  [Normal Traffic]
                   v                    v
          [ Node 1 (:5001) ]    [ Node 2 (:5002) ]
                   \                    /
                    \                  /
                     v                v
          [ Telemetry Agent & Anomaly Engine ]
                     |
                     v
             [ SQLite State Bus ] (cloud_telemetry.db)
                     |
                     v
          [ Streamlit Command Center :8501 ]
```

- **Multi-Node Workloads**: Flask instances simulating cloud VMs with CPU, memory, disk, and network stats via `psutil`.
- **Metric-Aware Load Balancer**: Shifts traffic away from degraded or overloaded nodes (CPU >= 80%) to healthy nodes with zero dropped requests.
- **Telemetry Agent**: Monitors node health every second, calculates SLA penalties, and debounces anomaly alerts (30s cooldown).
- **Command Center**: Minimal pastel Streamlit interface with live telemetry timelines, traffic distribution, topology map, and chaos controls.
- **Chaos Harness**: CLI and UI controls to inject CPU spikes and simulate concurrent HTTP traffic.

---

## File Structure

```
├── app_node.py          # Worker VM service with workload & chaos endpoints
├── load_balancer.py     # Reverse proxy with metric-aware failover (:8000)
├── agent.py             # Background telemetry polling & anomaly engine
├── shared_state.py      # SQLite bus for metrics, incidents, and routing logs
├── dashboard.py         # Streamlit command center (:8501)
├── svg_icons.py         # Minimalist vector SVG icon library
├── stress_test.py       # Load & chaos generator script
├── run_cluster.py       # Single-command orchestrator for all services
├── docker-compose.yml   # Containerized cluster setup
├── Dockerfile           # Docker build instructions
└── requirements.txt     # Python dependencies
```

---

## Quickstart

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Cluster

Start all services with a single command:

```bash
python run_cluster.py
```

This starts:
- **Dashboard**: http://localhost:8501
- **Load Balancer**: http://localhost:8000
- **Node 1**: http://localhost:5001
- **Node 2**: http://localhost:5002

---

## Live Chaos & Failover Demo

In a separate terminal, run the chaos test to observe automated traffic shifting:

```bash
# 1. Send normal baseline traffic (50/50 split across nodes)
python stress_test.py --traffic --rps 10 --duration 5

# 2. Inject heavy CPU load onto Node 1
python stress_test.py --stress-node1

# 3. Send traffic while Node 1 is overloaded
# -> 100% of traffic is automatically rerouted to Node 2
python stress_test.py --traffic --rps 15 --duration 5

# 4. Reset chaos condition
python stress_test.py --reset
```

---

## Docker Deployment

To run containerized via Docker Compose:

```bash
docker compose up --build
```
