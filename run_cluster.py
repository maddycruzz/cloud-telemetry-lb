#!/usr/bin/env python3
"""
Single-command orchestrator to start the entire Cloud Telemetry & Load Balancer system:
- Initializes SQLite shared state
- Starts Node 1 (port 5001)
- Starts Node 2 (port 5002)
- Starts Load Balancer (port 8000)
- Starts Telemetry Agent
- Starts Streamlit Command Center (port 8501)
"""

import subprocess
import time
import sys
import os
import signal

PYTHON_EXEC = sys.executable

processes = []

def signal_handler(sig, frame):
    print("\n[STOPPING] Shutting down cluster services...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            p.kill()
    print("[STOPPED] All services stopped safely.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def start_service(name, cmd):
    print(f"[STARTING] {name}...")
    p = subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    processes.append(p)
    return p

def main():
    print("=" * 60)
    print("  CLOUD TELEMETRY & ADAPTIVE LOAD BALANCING SYSTEM")
    print("=" * 60)

    # 1. Init DB
    subprocess.run([PYTHON_EXEC, "shared_state.py"], check=True)

    # 2. Start nodes
    start_service("Node 1 (:5001)", [PYTHON_EXEC, "app_node.py", "node-1", "5001"])
    start_service("Node 2 (:5002)", [PYTHON_EXEC, "app_node.py", "node-2", "5002"])
    time.sleep(1.5)

    # 3. Start Load Balancer
    start_service("Load Balancer (:8000)", [PYTHON_EXEC, "load_balancer.py"])
    time.sleep(1.0)

    # 4. Start Telemetry Agent
    start_service("Telemetry Agent", [PYTHON_EXEC, "agent.py"])
    time.sleep(1.0)

    # 5. Start Streamlit Dashboard
    print("[STARTING] Streamlit Command Center on http://localhost:8501 ...")
    start_service("Streamlit Dashboard (:8501)", [
        PYTHON_EXEC, "-m", "streamlit", "run", "dashboard.py",
        "--server.port", "8501",
        "--server.headless", "true"
    ])

    print("\n" + "=" * 60)
    print("  Cluster running successfully!")
    print("  - Dashboard:     http://localhost:8501")
    print("  - Load Balancer: http://localhost:8000")
    print("  - Node 1:        http://localhost:5001")
    print("  - Node 2:        http://localhost:5002")
    print("  Press Ctrl+C to terminate all services.")
    print("=" * 60 + "\n")

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
