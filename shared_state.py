import sqlite3
import time
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_telemetry.db")

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            timestamp REAL,
            node_id TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            net_io_mb REAL,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            timestamp TEXT,
            node_id TEXT,
            metric_type TEXT,
            value REAL,
            severity TEXT,
            details TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routing_logs (
            timestamp REAL,
            target_node TEXT,
            path TEXT,
            latency_ms REAL,
            status_code INTEGER DEFAULT 200
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS node_registry (
            node_id TEXT PRIMARY KEY,
            host TEXT,
            port INTEGER,
            last_seen REAL,
            is_active INTEGER DEFAULT 1
        )
    """)
    # Create indexes for fast querying in real-time dashboards
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_routing_time ON routing_logs(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_time ON incidents(timestamp);")
    conn.commit()
    conn.close()

def record_metric(node_id, cpu, mem, net_mb, status="HEALTHY", disk=0.0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), node_id, float(cpu), float(mem), float(disk), float(net_mb), str(status))
    )
    conn.commit()
    conn.close()

def log_incident(node_id, metric, val, severity="CRITICAL", details=""):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?)",
        (now_str, node_id, metric, float(val), severity, str(details))
    )
    conn.commit()
    conn.close()

def log_routing(target_node, path, latency_ms, status_code=200):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO routing_logs VALUES (?, ?, ?, ?, ?)",
        (time.time(), target_node, path, float(latency_ms), int(status_code))
    )
    conn.commit()
    conn.close()

def register_node(node_id, host="localhost", port=5001):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO node_registry (node_id, host, port, last_seen, is_active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(node_id) DO UPDATE SET
            host=excluded.host,
            port=excluded.port,
            last_seen=excluded.last_seen,
            is_active=1
    """, (node_id, host, port, time.time()))
    conn.commit()
    conn.close()

def get_latest_node_status(node_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT cpu_percent, memory_percent, disk_percent, net_io_mb, status, timestamp "
        "FROM metrics WHERE node_id = ? ORDER BY timestamp DESC LIMIT 1",
        (node_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "cpu": row["cpu_percent"],
            "memory": row["memory_percent"],
            "disk": row["disk_percent"],
            "net_mb": row["net_io_mb"],
            "status": row["status"],
            "timestamp": row["timestamp"]
        }
    return {"cpu": 0.0, "memory": 0.0, "disk": 0.0, "net_mb": 0.0, "status": "UNKNOWN", "timestamp": 0}

def get_all_latest_statuses():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.node_id, m.cpu_percent, m.memory_percent, m.disk_percent, m.net_io_mb, m.status, m.timestamp
        FROM metrics m
        INNER JOIN (
            SELECT node_id, MAX(timestamp) as max_t
            FROM metrics
            GROUP BY node_id
        ) latest ON m.node_id = latest.node_id AND m.timestamp = latest.max_t
    """)
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["node_id"]] = {
            "cpu": r["cpu_percent"],
            "memory": r["memory_percent"],
            "disk": r["disk_percent"],
            "net_mb": r["net_io_mb"],
            "status": r["status"],
            "timestamp": r["timestamp"]
        }
    return result

def clear_all_data():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metrics;")
    cursor.execute("DELETE FROM incidents;")
    cursor.execute("DELETE FROM routing_logs;")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_NAME)
