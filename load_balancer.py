import time
import requests
from flask import Flask, jsonify, request, Response
from shared_state import get_latest_node_status, log_routing, init_db

app = Flask(__name__)

NODES = [
    {"id": "node-1", "url": "http://localhost:5001", "port": 5001},
    {"id": "node-2", "url": "http://localhost:5002", "port": 5002}
]

rr_counter = 0

def select_target_node():
    """
    Intelligent Metric-Aware Routing Algorithm:
    - Queries latest telemetry metrics from SQLite bus
    - If one node is overloaded (CPU >= 80% or OFFLINE/DEGRADED), routes 100% of traffic to the healthy node
    - If both are healthy (or both stressed), falls back to round-robin
    """
    global rr_counter
    node1_status = get_latest_node_status("node-1")
    node2_status = get_latest_node_status("node-2")

    n1_cpu = node1_status.get("cpu", 0.0)
    n2_cpu = node2_status.get("cpu", 0.0)
    n1_healthy = (node1_status.get("status") == "HEALTHY") and (n1_cpu < 80.0)
    n2_healthy = (node2_status.get("status") == "HEALTHY") and (n2_cpu < 80.0)

    # Adaptive Failover Policies
    if not n1_healthy and n2_healthy:
        # Node 1 degraded/overloaded -> Route to Node 2
        return NODES[1], "FAILOVER_TO_NODE_2", n1_cpu, n2_cpu

    if not n2_healthy and n1_healthy:
        # Node 2 degraded/overloaded -> Route to Node 1
        return NODES[0], "FAILOVER_TO_NODE_1", n1_cpu, n2_cpu

    # If both healthy or both strained, alternate using round-robin
    chosen = NODES[rr_counter % len(NODES)]
    rr_counter += 1
    return chosen, "BALANCED_ROUND_ROBIN", n1_cpu, n2_cpu

@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    target, mode, n1_cpu, n2_cpu = select_target_node()
    url = f"{target['url']}/{path}"

    start = time.time()
    try:
        # Forward request to chosen node
        resp = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key.lower() != 'host'},
            data=request.get_data(),
            params=request.args,
            timeout=3.0
        )
        latency = (time.time() - start) * 1000.0
        log_routing(target["id"], f"/{path}", latency, resp.status_code)

        # Return downstream response with custom tracking headers
        headers = dict(resp.headers)
        headers["X-Handled-By"] = target["id"]
        headers["X-Routing-Mode"] = mode
        headers["X-Upstream-Latency-Ms"] = f"{latency:.2f}"
        return Response(resp.content, resp.status_code, headers)

    except Exception as e:
        latency = (time.time() - start) * 1000.0
        log_routing(target["id"], f"/{path}", latency, 502)

        # Self-healing fallback: attempt alternative node if primary fails
        alt_node = NODES[1] if target["id"] == "node-1" else NODES[0]
        try:
            alt_url = f"{alt_node['url']}/{path}"
            resp = requests.request(
                method=request.method,
                url=alt_url,
                headers={key: value for (key, value) in request.headers if key.lower() != 'host'},
                data=request.get_data(),
                params=request.args,
                timeout=3.0
            )
            alt_latency = (time.time() - start) * 1000.0
            log_routing(alt_node["id"], f"/{path}", alt_latency, resp.status_code)
            headers = dict(resp.headers)
            headers["X-Handled-By"] = f"{alt_node['id']}-FALLBACK"
            return Response(resp.content, resp.status_code, headers)
        except Exception as alt_err:
            return jsonify({
                "error": "All backend nodes unreachable",
                "primary_node": target["id"],
                "primary_error": str(e),
                "fallback_error": str(alt_err)
            }), 503

@app.route("/lb/status")
def lb_status():
    node1_status = get_latest_node_status("node-1")
    node2_status = get_latest_node_status("node-2")
    return jsonify({
        "status": "online",
        "port": 8000,
        "nodes": {
            "node-1": node1_status,
            "node-2": node2_status
        }
    })

if __name__ == "__main__":
    init_db()
    print("Adaptive Metric-Aware Load Balancer running on port 8000...")
    app.run(host="0.0.0.0", port=8000, threaded=True)
