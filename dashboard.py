import time
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import requests

from svg_icons import (
    icon_settings,
    icon_zap,
    icon_traffic,
    icon_refresh,
    icon_cloud,
    icon_clients,
    icon_balancer,
    icon_server,
    icon_arrow_right,
    icon_check_circle,
    icon_alert_triangle,
    icon_dot
)

# Set page configuration with clean title and layout
st.set_page_config(
    page_title="Cloud Telemetry & Load Balancer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom minimal & pastel CSS styling
PASTEL_CSS = """
<style>
    /* Clean, modern typography and background */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #2D3748;
    }

    /* Minimal card container */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #EAEAEA;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
    }

    .metric-title {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #718096;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #1A202C;
        line-height: 1.2;
    }

    /* Pastel status badges */
    .badge-healthy {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background-color: #EBF5EE;
        color: #2E6B4B;
        border: 1px solid #D1EADE;
    }

    .badge-overload {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background-color: #FDF0ED;
        color: #B24330;
        border: 1px solid #F8D3CB;
    }

    .badge-warning {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background-color: #FEF9EC;
        color: #926618;
        border: 1px solid #FCE8BD;
    }

    .badge-neutral {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background-color: #F0F4F8;
        color: #3B5A79;
        border: 1px solid #DCE6F0;
    }

    /* Streamlit element overrides for clean minimalism */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 16px;
        border-radius: 8px;
        font-weight: 500;
        color: #718096;
        border: none;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2D3748 !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
</style>
"""
st.markdown(PASTEL_CSS, unsafe_allow_html=True)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_telemetry.db")

# Color palette: soft pastel tones (non-neon)
COLOR_NODE1 = "#5E81AC"       # Pastel Slate Blue
COLOR_NODE2 = "#88C0D0"       # Pastel Soft Teal / Frost
COLOR_STRESS = "#D08770"      # Pastel Dusty Coral / Clay
COLOR_HEALTHY = "#A3BE8C"     # Pastel Sage Green
COLOR_WARNING = "#EBCB8B"     # Pastel Warm Butter / Sand
COLOR_ACCENT = "#B48EAD"      # Pastel Soft Lavender

def get_connection():
    return sqlite3.connect(DB_PATH, timeout=10.0)

def fetch_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    conn = get_connection()
    try:
        # Fetch metrics from the last 3 minutes
        query_m = """
            SELECT timestamp, node_id, cpu_percent, memory_percent, disk_percent, net_io_mb, status
            FROM metrics
            WHERE timestamp >= (strftime('%s', 'now') - 180)
            ORDER BY timestamp ASC
        """
        df_m = pd.read_sql_query(query_m, conn)
        if not df_m.empty:
            df_m["datetime"] = pd.to_datetime(df_m["timestamp"], unit='s')

        # Fetch recent incident logs
        query_i = """
            SELECT timestamp, node_id, metric_type, value, severity, details
            FROM incidents
            ORDER BY rowid DESC
            LIMIT 15
        """
        df_i = pd.read_sql_query(query_i, conn)

        # Fetch recent routing logs (last 2 minutes)
        query_r = """
            SELECT timestamp, target_node, path, latency_ms, status_code
            FROM routing_logs
            WHERE timestamp >= (strftime('%s', 'now') - 120)
            ORDER BY timestamp DESC
        """
        df_r = pd.read_sql_query(query_r, conn)

        return df_m, df_i, df_r
    except Exception as e:
        st.error(f"Database query error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    finally:
        conn.close()

# --- Sidebar Controls ---
st.sidebar.markdown(f"<div style='font-size: 14px; font-weight: 700; color: #1E293B; margin-bottom: 12px;'>{icon_settings(16, '#4A6B82')} Cluster Configuration</div>", unsafe_allow_html=True)
auto_refresh = st.sidebar.toggle("Live Telemetry Stream", value=True)
refresh_rate = st.sidebar.slider("Refresh Interval (seconds)", min_value=1, max_value=5, value=2)

st.sidebar.markdown("---")
st.sidebar.markdown(f"<div style='font-size: 14px; font-weight: 700; color: #1E293B; margin-bottom: 8px;'>{icon_zap(16, '#D08770')} Live Chaos Control</div>", unsafe_allow_html=True)
st.sidebar.caption("Inject hardware stress to test automated self-healing routing.")

col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    if st.button("Stress Node-1", use_container_width=True):
        try:
            requests.get("http://localhost:5001/chaos/inject?cpu=94.5", timeout=1)
            st.sidebar.success("Node-1 CPU overloaded (94.5%)")
        except Exception:
            st.sidebar.error("Node-1 unreachable on :5001")

with col_c2:
    if st.button("Stress Node-2", use_container_width=True):
        try:
            requests.get("http://localhost:5002/chaos/inject?cpu=93.0", timeout=1)
            st.sidebar.success("Node-2 CPU overloaded (93.0%)")
        except Exception:
            st.sidebar.error("Node-2 unreachable on :5002")

if st.sidebar.button("Reset Chaos (Restore Normal)", use_container_width=True):
    for port in [5001, 5002]:
        try:
            requests.get(f"http://localhost:{port}/chaos/reset", timeout=1)
        except Exception:
            pass
    st.sidebar.info("All nodes returned to normal telemetry.")

st.sidebar.markdown("---")
st.sidebar.markdown(f"<div style='font-size: 14px; font-weight: 700; color: #1E293B; margin-bottom: 8px;'>{icon_traffic(16, '#5E81AC')} Traffic Generator</div>", unsafe_allow_html=True)
burst_count = st.sidebar.number_input("Request Batch Size", min_value=5, max_value=100, value=20, step=5)
if st.sidebar.button("Send Test Traffic Batch", use_container_width=True):
    success_ct = 0
    with st.spinner(f"Sending {burst_count} requests through Load Balancer (:8000)..."):
        for _ in range(int(burst_count)):
            try:
                r = requests.get("http://localhost:8000/workload", timeout=1.5)
                if r.status_code == 200:
                    success_ct += 1
            except Exception:
                pass
            time.sleep(0.04)
    st.sidebar.success(f"Dispatched {burst_count} requests ({success_ct} succeeded)")

# --- Data Fetching ---
df_metrics, df_incidents, df_routing = fetch_data()

# Latest node stats extraction
n1_latest = None
n2_latest = None

if not df_metrics.empty:
    df_n1 = df_metrics[df_metrics["node_id"] == "node-1"]
    if not df_n1.empty:
        n1_latest = df_n1.iloc[-1]

    df_n2 = df_metrics[df_metrics["node_id"] == "node-2"]
    if not df_n2.empty:
        n2_latest = df_n2.iloc[-1]

n1_cpu = n1_latest["cpu_percent"] if n1_latest is not None else 0.0
n2_cpu = n2_latest["cpu_percent"] if n2_latest is not None else 0.0
n1_mem = n1_latest["memory_percent"] if n1_latest is not None else 0.0
n2_mem = n2_latest["memory_percent"] if n2_latest is not None else 0.0
n1_status = n1_latest["status"] if n1_latest is not None else "OFFLINE"
n2_status = n2_latest["status"] if n2_latest is not None else "OFFLINE"

# Routing state evaluation
if n1_cpu >= 80.0 and n2_cpu < 80.0:
    routing_mode = "FAILOVER TO NODE-2"
    routing_badge_class = "badge-warning"
    dot_color = "#926618"
elif n2_cpu >= 80.0 and n1_cpu < 80.0:
    routing_mode = "FAILOVER TO NODE-1"
    routing_badge_class = "badge-warning"
    dot_color = "#926618"
elif n1_cpu >= 80.0 and n2_cpu >= 80.0:
    routing_mode = "DUAL SATURATION DEGRADED"
    routing_badge_class = "badge-overload"
    dot_color = "#B24330"
else:
    routing_mode = "BALANCED ROUND-ROBIN"
    routing_badge_class = "badge-healthy"
    dot_color = "#2E6B4B"

# SLA calculation ($0.05 per metric interval with CPU >= 80%)
sla_violations = len(df_metrics[df_metrics["cpu_percent"] >= 80.0]) if not df_metrics.empty else 0
sla_penalty_cost = sla_violations * 0.05

# Total requests handled in last 2 mins
total_recent_requests = len(df_routing) if not df_routing.empty else 0

# --- Dashboard Header ---
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown("<h2 style='margin-bottom: 2px; font-weight: 700; color: #1E293B;'>Cloud Telemetry & Adaptive Load Balancing</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 14px; margin-top: 0;'>Autonomous real-time health telemetry, threshold debouncing & self-healing traffic rerouting</p>", unsafe_allow_html=True)

with header_col2:
    status_pill = f"<div style='text-align: right; padding-top: 8px;'><span class='{routing_badge_class}'>{icon_dot(dot_color)} {routing_mode}</span></div>"
    st.markdown(status_pill, unsafe_allow_html=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# --- Top Metric Cards ---
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    badge = "badge-healthy" if n1_cpu < 80.0 and n1_status != "OFFLINE" else "badge-overload"
    c_dot = "#2E6B4B" if n1_cpu < 80.0 and n1_status != "OFFLINE" else "#B24330"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Node 1 (Port 5001)</div>
        <div class="metric-value">{n1_cpu:.1f}%</div>
        <div style="margin-top: 8px;">
            <span class="{badge}">{icon_dot(c_dot)} {n1_status}</span>
            <span style="font-size: 12px; color: #718096; margin-left: 6px;">RAM: {n1_mem:.0f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    badge = "badge-healthy" if n2_cpu < 80.0 and n2_status != "OFFLINE" else "badge-overload"
    c_dot = "#2E6B4B" if n2_cpu < 80.0 and n2_status != "OFFLINE" else "#B24330"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Node 2 (Port 5002)</div>
        <div class="metric-value">{n2_cpu:.1f}%</div>
        <div style="margin-top: 8px;">
            <span class="{badge}">{icon_dot(c_dot)} {n2_status}</span>
            <span style="font-size: 12px; color: #718096; margin-left: 6px;">RAM: {n2_mem:.0f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Active Routing Policy</div>
        <div style="font-size: 18px; font-weight: 700; color: #1A202C; margin-top: 4px; line-height: 1.3;">
            {routing_mode}
        </div>
        <div style="margin-top: 8px;">
            <span class="badge-neutral">{icon_dot('#3B5A79')} Proxy :8000</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Recent Routed Requests</div>
        <div class="metric-value">{total_recent_requests}</div>
        <div style="margin-top: 8px;">
            <span class="badge-neutral">{icon_dot('#3B5A79')} Past 2 Mins</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c5:
    penalty_badge = "badge-healthy" if sla_penalty_cost == 0 else "badge-overload"
    p_dot = "#2E6B4B" if sla_penalty_cost == 0 else "#B24330"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">SLA Penalty Incurred</div>
        <div class="metric-value">${sla_penalty_cost:.2f}</div>
        <div style="margin-top: 8px;">
            <span class="{penalty_badge}">{icon_dot(p_dot)} {sla_violations} Breaches</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# --- Navigation Tabs (Clean minimal text tabs) ---
tab_telemetry, tab_distribution, tab_architecture, tab_incidents = st.tabs([
    "Telemetry Timeline",
    "Routing & Latency",
    "Topology & Flow",
    "Anomaly & Webhook Log"
])

# --- TAB 1: Live Telemetry Charts ---
with tab_telemetry:
    chart_left, chart_right = st.columns([2, 1])

    with chart_left:
        st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Node CPU Saturation Timeline (Past 3 Mins)</h4>", unsafe_allow_html=True)
        if not df_metrics.empty and "datetime" in df_metrics.columns:
            fig_cpu = px.line(
                df_metrics,
                x="datetime",
                y="cpu_percent",
                color="node_id",
                color_discrete_map={"node-1": "#4C72B0", "node-2": "#55A868"},
                labels={"cpu_percent": "CPU Usage (%)", "datetime": "Time", "node_id": "Cluster Node"}
            )
            fig_cpu.update_layout(
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAFAFA",
                margin=dict(l=40, r=20, t=20, b=40),
                height=320,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(showgrid=True, gridcolor="#EEEEEE"),
                yaxis=dict(range=[0, 105], showgrid=True, gridcolor="#EEEEEE")
            )
            # Threshold line in soft pastel terracotta
            fig_cpu.add_hline(
                y=80,
                line_dash="dot",
                line_color="#C06C84",
                line_width=1.5,
                annotation_text="SLA Threshold (80%)",
                annotation_font=dict(size=11, color="#C06C84"),
                annotation_position="bottom right"
            )
            st.plotly_chart(fig_cpu, use_container_width=True)
        else:
            st.info("Awaiting telemetry stream from background agent... (Start agent.py to populate)")

    with chart_right:
        st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Current Node Resource Gauges</h4>", unsafe_allow_html=True)

        # Clean pastel horizontal bars for node metrics
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown(f"**Node 1: {n1_cpu:.1f}% CPU**")
            st.progress(min(1.0, max(0.0, n1_cpu / 100.0)))
            st.caption(f"RAM: {n1_mem:.1f}% | Disk: {n1_latest['disk_percent'] if n1_latest is not None else 0.0:.0f}%")

        with col_g2:
            st.markdown(f"**Node 2: {n2_cpu:.1f}% CPU**")
            st.progress(min(1.0, max(0.0, n2_cpu / 100.0)))
            st.caption(f"RAM: {n2_mem:.1f}% | Disk: {n2_latest['disk_percent'] if n2_latest is not None else 0.0:.0f}%")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        # Network I/O bar chart
        if not df_metrics.empty:
            df_net = df_metrics.groupby("node_id")["net_io_mb"].last().reset_index()
            fig_net = px.bar(
                df_net,
                x="node_id",
                y="net_io_mb",
                color="node_id",
                color_discrete_map={"node-1": "#81A1C1", "node-2": "#8FBCBB"},
                labels={"net_io_mb": "Network (MB/s)", "node_id": "Node"}
            )
            fig_net.update_layout(
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAFAFA",
                height=180,
                margin=dict(l=30, r=20, t=10, b=30),
                showlegend=False,
                yaxis=dict(showgrid=True, gridcolor="#EEEEEE")
            )
            st.plotly_chart(fig_net, use_container_width=True)

# --- TAB 2: Traffic Routing & Latency ---
with tab_distribution:
    dist_c1, dist_c2 = st.columns([1, 1])

    with dist_c1:
        st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Traffic Distribution (Recent Requests)</h4>", unsafe_allow_html=True)
        if not df_routing.empty:
            traffic_counts = df_routing["target_node"].value_counts().reset_index()
            traffic_counts.columns = ["node", "requests"]

            fig_donut = px.pie(
                traffic_counts,
                values="requests",
                names="node",
                hole=0.55,
                color="node",
                color_discrete_map={
                    "node-1": "#4C72B0",
                    "node-2": "#55A868",
                    "node-1-FALLBACK": "#EBCB8B",
                    "node-2-FALLBACK": "#EBCB8B"
                }
            )
            fig_donut.update_layout(
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAFAFA",
                margin=dict(l=20, r=20, t=20, b=20),
                height=260,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No incoming user traffic recorded yet. Use the sidebar 'Send Test Traffic Batch' or run `stress_test.py --traffic`.")

    with dist_c2:
        st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Upstream Execution Latency (ms)</h4>", unsafe_allow_html=True)
        if not df_routing.empty:
            df_routing["request_idx"] = range(len(df_routing))
            fig_lat = px.scatter(
                df_routing.head(50),
                x="latency_ms",
                y="target_node",
                color="target_node",
                color_discrete_map={"node-1": "#4C72B0", "node-2": "#55A868"},
                size=[10] * len(df_routing.head(50)),
                labels={"latency_ms": "Latency (ms)", "target_node": "Target"}
            )
            fig_lat.update_layout(
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FAFAFA",
                margin=dict(l=40, r=20, t=20, b=40),
                height=260,
                showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#EEEEEE")
            )
            st.plotly_chart(fig_lat, use_container_width=True)
        else:
            st.info("No latency data yet.")

    # Recent routing log entries
    st.markdown("<h4 style='font-size: 14px; font-weight: 600; color: #2D3748;'>Live Request Audit (Last 10 Records)</h4>", unsafe_allow_html=True)
    if not df_routing.empty:
        display_routing = df_routing[["timestamp", "target_node", "path", "latency_ms", "status_code"]].head(10).copy()
        display_routing["time"] = pd.to_datetime(display_routing["timestamp"], unit='s').dt.strftime('%H:%M:%S')
        display_routing = display_routing.drop(columns=["timestamp"])
        st.dataframe(display_routing, use_container_width=True, hide_index=True)

# --- TAB 3: Topology & Health Flow ---
with tab_architecture:
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 12px;'>Autonomous Topology & Traffic Flow</h4>", unsafe_allow_html=True)

    # Topology representation using clean pastel HTML cards with pure SVGs
    n1_color = "#EBF5EE" if n1_cpu < 80.0 else "#FDF0ED"
    n1_border = "#BCE3C5" if n1_cpu < 80.0 else "#F5B8AC"
    n2_color = "#EBF5EE" if n2_cpu < 80.0 else "#FDF0ED"
    n2_border = "#BCE3C5" if n2_cpu < 80.0 else "#F5B8AC"

    n1_status_indicator = f"{icon_check_circle(14, '#2E6B4B')} ACTIVE (Receiving Traffic)" if (n1_cpu < 80.0) else f"{icon_alert_triangle(14, '#B24330')} SHUNTED (Traffic Diverted)"
    n2_status_indicator = f"{icon_check_circle(14, '#2E6B4B')} ACTIVE (Receiving Traffic)" if (n2_cpu < 80.0) else f"{icon_alert_triangle(14, '#B24330')} SHUNTED (Traffic Diverted)"

    topo_html = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; background: #FFFFFF; padding: 24px; border-radius: 12px; border: 1px solid #EAEAEA;">
        <!-- Client -->
        <div style="flex: 1; text-align: center; background: #F8F9FA; border: 1px solid #E2E8F0; padding: 18px; border-radius: 8px;">
            <div style="margin-bottom: 6px;">{icon_clients(28, '#5B7083')}</div>
            <div style="font-weight: 700; color: #2D3748;">User Clients</div>
            <div style="font-size: 12px; color: #718096; margin-top: 2px;">HTTP Ingress</div>
        </div>

        <div>{icon_arrow_right(20, '#A0AEC0')}</div>

        <!-- Load Balancer -->
        <div style="flex: 1.5; text-align: center; background: #F0F4F8; border: 1px solid #D0DFEE; padding: 18px; border-radius: 8px;">
            <div style="margin-bottom: 6px;">{icon_balancer(28, '#4A6B82')}</div>
            <div style="font-weight: 700; color: #2B4C6F;">Metric-Aware Load Balancer</div>
            <div style="font-size: 12px; color: #4A6B82; margin-top: 2px;">Port 8000 | Mode: <strong>{routing_mode}</strong></div>
        </div>

        <div>{icon_arrow_right(20, '#A0AEC0')}</div>

        <!-- Nodes Stack -->
        <div style="flex: 2; display: flex; flex-direction: column; gap: 12px;">
            <div style="background: {n1_color}; border: 1px solid {n1_border}; padding: 14px 18px; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #2D3748;">Node 1 (:5001)</span>
                    <span style="font-size: 12px; font-weight: 600;">{n1_cpu:.1f}% CPU</span>
                </div>
                <div style="font-size: 12px; color: #4A5568; margin-top: 4px; display: flex; align-items: center;">{n1_status_indicator}</div>
            </div>

            <div style="background: {n2_color}; border: 1px solid {n2_border}; padding: 14px 18px; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #2D3748;">Node 2 (:5002)</span>
                    <span style="font-size: 12px; font-weight: 600;">{n2_cpu:.1f}% CPU</span>
                </div>
                <div style="font-size: 12px; color: #4A5568; margin-top: 4px; display: flex; align-items: center;">{n2_status_indicator}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(topo_html, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    st.markdown("""
    **Self-Healing Algorithm Explained:**
    1. **Telemetry Ingestion**: Worker nodes report real-time CPU, RAM, and hardware metrics every second to the shared SQLite state bus.
    2. **Anomaly Detection**: If node CPU crosses 80.0%, the monitoring agent fires a debounced alert incident.
    3. **Dynamic Proxy Routing**: The Load Balancer queries the shared state before routing. Overloaded nodes are immediately bypassed in favor of healthy nodes.
    4. **Zero Dropped Requests**: If a primary target becomes completely unresponsive during transit, the proxy automatically falls back to an alternate node.
    """)

# --- TAB 4: Anomaly Log & Webhooks ---
with tab_incidents:
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Incident & Alert Log (Threshold Debounced)</h4>", unsafe_allow_html=True)

    if not df_incidents.empty:
        st.dataframe(df_incidents, use_container_width=True, hide_index=True)
    else:
        st.info("No anomalies detected yet. System is operating within SLA boundaries.")

    st.markdown("<hr style='border: none; border-top: 1px solid #EAEAEA; margin: 20px 0;'>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size: 14px; font-weight: 600; color: #2D3748; margin-bottom: 8px;'>Webhook Alert Preview (Slack / Discord Format)</h4>", unsafe_allow_html=True)

    sample_webhook_payload = {
        "content": "[ALERT] Cloud Anomaly Detected\nNode: node-1\nMetric: CPU at 94.50% (Threshold: 80.0%)\nAction: Load Balancer redirecting traffic away from this node.",
        "text": "[Cloud Alert] Node node-1 breached CPU threshold: 94.50%"
    }
    st.json(sample_webhook_payload)

# --- Auto Refresh Script ---
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
