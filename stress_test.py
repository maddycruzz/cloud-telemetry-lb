import argparse
import multiprocessing
import time
import requests
import sys

def stress_cpu_spin(duration):
    """Heavy mathematical calculations to saturate CPU cores"""
    end = time.time() + duration
    while time.time() < end:
        _ = 999999 * 999999

def trigger_node_chaos(port=5001, cpu=92.5, duration=30):
    """Instruct node to simulate heavy hardware load"""
    try:
        url = f"http://localhost:{port}/chaos/inject?cpu={cpu}"
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            print(f"[CHAOS INJECTED] Node on port {port}: simulated CPU={cpu}%")
    except Exception as e:
        print(f"Warning: Could not contact node on port {port}: {e}")

def reset_node_chaos(port=5001):
    try:
        url = f"http://localhost:{port}/chaos/reset"
        requests.get(url, timeout=2)
        print(f"[CHAOS RESET] Restored normal health on node (port {port})")
    except Exception as e:
        print(f"Warning: Could not contact node on port {port}: {e}")

def send_traffic(rps=15, duration=45, lb_url="http://localhost:8000/workload"):
    end = time.time() + duration
    print(f"[TRAFFIC] Simulating production traffic to Load Balancer ({lb_url})")
    print(f"   Rate: {rps} requests/second | Duration: {duration} seconds\n")

    success_count = 0
    fail_count = 0
    routes = {}

    while time.time() < end:
        req_start = time.time()
        try:
            resp = requests.get(lb_url, timeout=2.0)
            if resp.status_code == 200:
                success_count += 1
                handled_by = resp.headers.get("X-Handled-By", "unknown")
                routes[handled_by] = routes.get(handled_by, 0) + 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1

        elapsed = time.time() - req_start
        sleep_time = max(0.0, (1.0 / rps) - elapsed)
        time.sleep(sleep_time)

    print(f"\n[TRAFFIC COMPLETE] Simulation finished:")
    print(f"   Total Requests: {success_count + fail_count} | Success: {success_count} | Failed: {fail_count}")
    print(f"   Traffic Distribution: {routes}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud Telemetry & Load Balancer Chaos Harness")
    parser.add_argument("--stress-node1", action="store_true", help="Saturate CPU on Node-1 (port 5001)")
    parser.add_argument("--stress-node2", action="store_true", help="Saturate CPU on Node-2 (port 5002)")
    parser.add_argument("--traffic", action="store_true", help="Send user traffic to Load Balancer")
    parser.add_argument("--rps", type=int, default=15, help="Requests per second (default: 15)")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds (default: 30)")
    parser.add_argument("--reset", action="store_true", help="Reset all chaos conditions to normal")
    parser.add_argument("--spin-cores", action="store_true", help="Spawn real multiprocessing CPU burn loops")
    args = parser.parse_args()

    if args.reset:
        reset_node_chaos(5001)
        reset_node_chaos(5002)
        sys.exit(0)

    if args.stress_node1:
        trigger_node_chaos(port=5001, cpu=94.0, duration=args.duration)
        if args.spin_cores:
            print("Launching multi-core CPU burn loop...")
            procs = [multiprocessing.Process(target=stress_cpu_spin, args=(args.duration,)) for _ in range(multiprocessing.cpu_count())]
            for p in procs: p.start()

    if args.stress_node2:
        trigger_node_chaos(port=5002, cpu=94.0, duration=args.duration)
        if args.spin_cores:
            print("Launching multi-core CPU burn loop...")
            procs = [multiprocessing.Process(target=stress_cpu_spin, args=(args.duration,)) for _ in range(multiprocessing.cpu_count())]
            for p in procs: p.start()

    if args.traffic:
        send_traffic(rps=args.rps, duration=args.duration)
