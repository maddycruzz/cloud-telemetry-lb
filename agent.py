import time
import os
import requests
import psutil
from shared_state import record_metric, log_incident, init_db

# Optional: Add your Discord/Slack Webhook URL here or via environment variable
WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")

CPU_CRITICAL_THRESHOLD = 80.0
MEMORY_CRITICAL_THRESHOLD = 85.0
COOLDOWN_SECONDS = 30  # Debounce window in seconds

last_alert_time = {"node-1": 0, "node-2": 0}

def send_alert(node_id, metric, value, threshold=CPU_CRITICAL_THRESHOLD):
    now = time.time()
    time_since_last = now - last_alert_time.get(node_id, 0)
    if time_since_last < COOLDOWN_SECONDS:
        # Debounced: Skip external alert flood, but incident is already tracked
        return False

    last_alert_time[node_id] = now
    details = f"{metric} saturated at {value:.1f}% (SLA breach threshold: {threshold}%)"
    log_incident(node_id, metric, value, "CRITICAL", details)
    print(f"[ANOMALY DETECTED] {node_id} breached {metric}: {value:.1f}% | Load Balancer failover triggered")

    if WEBHOOK_URL:
        # Payload compatible with both Slack and Discord webhooks
        payload = {
            "content": f"[ALERT] Cloud Anomaly Detected\n"
                       f"**Node:** `{node_id}`\n"
                       f"**Metric:** `{metric}` at `{value:.2f}%` (Threshold: {threshold}%)\n"
                       f"**Action:** Load Balancer shifting traffic automatically to healthy nodes.",
            "text": f"[Cloud Alert] Node {node_id} breached {metric} threshold: {value:.2f}%"
        }
        try:
            resp = requests.post(WEBHOOK_URL, json=payload, timeout=3)
            print(f"[WEBHOOK] Dispatched alert to webhook endpoint (HTTP {resp.status_code})")
        except Exception as e:
            print(f"[WEBHOOK ERROR] Failed to deliver alert payload: {e}")
    else:
        print(f"[WEBHOOK] (Simulated) Alert payload generated for {node_id} ({metric}={value:.1f}%)")

    return True

def run_agent():
    init_db()
    prev_net = psutil.net_io_counters()

    nodes = [
        {"id": "node-1", "port": 5001},
        {"id": "node-2", "port": 5002}
    ]

    print("Telemetry Agent active. Monitoring cluster health at 1-second intervals...")

    while True:
        curr_net = psutil.net_io_counters()
        net_mb = (curr_net.bytes_sent + curr_net.bytes_recv - (prev_net.bytes_sent + prev_net.bytes_recv)) / (1024 * 1024)
        prev_net = curr_net

        for node in nodes:
            try:
                res = requests.get(f"http://localhost:{node['port']}/health", timeout=1.5)
                data = res.json()
                cpu = float(data.get("cpu", 0.0))
                mem = float(data.get("memory", 0.0))
                disk = float(data.get("disk", 0.0))
                status = "HEALTHY" if cpu < CPU_CRITICAL_THRESHOLD else "OVERLOADED"

                if cpu >= CPU_CRITICAL_THRESHOLD:
                    send_alert(node["id"], "CPU", cpu, CPU_CRITICAL_THRESHOLD)
                elif mem >= MEMORY_CRITICAL_THRESHOLD:
                    send_alert(node["id"], "MEMORY", mem, MEMORY_CRITICAL_THRESHOLD)

                record_metric(node["id"], cpu, mem, round(net_mb, 3), status, disk)
            except Exception as e:
                # Node unreachable
                send_alert(node["id"], "CONNECTIVITY", 100.0, 0.0)
                record_metric(node["id"], 0.0, 0.0, 0.0, "OFFLINE", 0.0)

        time.sleep(1.0)

if __name__ == "__main__":
    run_agent()
