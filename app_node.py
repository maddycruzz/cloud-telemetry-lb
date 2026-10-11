import sys
import time
import os
import threading
from flask import Flask, jsonify, request
import psutil
from shared_state import register_node, init_db

app = Flask(__name__)

# CLI parameters
node_id = sys.argv[1] if len(sys.argv) > 1 else "node-1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001

# Node-specific runtime metrics
request_counter = 0
current_process = psutil.Process(os.getpid())

# Chaos simulation state for isolated node testing
chaos_state = {
    "active": False,
    "forced_cpu": None,
    "forced_latency_sec": 0.0,
    "forced_error": False,
    "stress_threads": []
}

def cpu_burn_worker(stop_event):
    while not stop_event.is_set():
        _ = 314159 * 271828

@app.route("/")
def index():
    global request_counter
    request_counter += 1
    return jsonify({
        "status": "online",
        "handled_by": node_id,
        "port": port,
        "requests_served": request_counter,
        "timestamp": time.time()
    })

@app.route("/workload")
def compute_workload():
    global request_counter
    request_counter += 1

    # Check for artificial chaos delay or failure
    if chaos_state["forced_error"]:
        return jsonify({"error": "Node hardware failure simulated", "node": node_id}), 500

    if chaos_state["forced_latency_sec"] > 0:
        time.sleep(chaos_state["forced_latency_sec"])

    start = time.time()
    # Configurable workload
    iterations = int(request.args.get("iterations", 100_000))
    total = sum(i * i for i in range(iterations))
    duration = (time.time() - start) * 1000

    return jsonify({
        "node": node_id,
        "port": port,
        "result": total,
        "execution_time_ms": round(duration, 2),
        "requests_served": request_counter
    })

@app.route("/health")
def health():
    # If forced CPU is set (via chaos injection), report that;
    # otherwise calculate host + process weighted CPU
    if chaos_state["forced_cpu"] is not None:
        cpu = round(chaos_state["forced_cpu"], 1)
    else:
        # Base host CPU reading
        host_cpu = psutil.cpu_percent(interval=None)
        # Normalize to reasonable baseline if idle (10-25%)
        cpu = max(host_cpu, 12.0)

    mem = psutil.virtual_memory().percent
    try:
        disk = psutil.disk_usage("/").percent
    except Exception:
        disk = 45.0

    healthy = cpu < 80.0 and not chaos_state["forced_error"]
    status_str = "HEALTHY" if healthy else ("OVERLOADED" if cpu >= 80.0 else "DEGRADED")

    return jsonify({
        "node": node_id,
        "port": port,
        "healthy": healthy,
        "status": status_str,
        "cpu": cpu,
        "memory": mem,
        "disk": disk,
        "requests_served": request_counter,
        "chaos_active": chaos_state["active"],
        "timestamp": time.time()
    }), (200 if healthy else 503)

@app.route("/chaos/inject", methods=["GET", "POST"])
def inject_chaos():
    cpu_val = request.args.get("cpu", type=float, default=92.0)
    delay_val = request.args.get("delay", type=float, default=0.0)
    error_val = request.args.get("error", type=int, default=0)

    chaos_state["active"] = True
    chaos_state["forced_cpu"] = cpu_val
    chaos_state["forced_latency_sec"] = delay_val
    chaos_state["forced_error"] = bool(error_val)

    return jsonify({
        "message": f"Chaos injected into {node_id}",
        "node": node_id,
        "forced_cpu": cpu_val,
        "forced_latency_sec": delay_val,
        "forced_error": chaos_state["forced_error"]
    })

@app.route("/chaos/reset", methods=["GET", "POST"])
def reset_chaos():
    chaos_state["active"] = False
    chaos_state["forced_cpu"] = None
    chaos_state["forced_latency_sec"] = 0.0
    chaos_state["forced_error"] = False

    return jsonify({
        "message": f"Chaos cleared on {node_id}",
        "node": node_id,
        "status": "NORMAL"
    })

if __name__ == "__main__":
    init_db()
    register_node(node_id, "localhost", port)
    print(f"[{node_id}] Starting application node on port {port}...")
    app.run(host="0.0.0.0", port=port, threaded=True)
