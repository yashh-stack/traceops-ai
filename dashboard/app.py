"""
TraceOps AI: Live Jury Control Room & Circuit-Breaker HUD.
Minimalist, high-performance dark-mode interface built for
Google DeepMind x Cloud Startup Buildathon India 2026.

Architectural Invariant:
"LLMs advise. The deterministic state machine decides."
Hot path runs synchronously on CPU (<15 ms).
Async cold path runs via OpenTelemetry + Gemini 3.5 Flash Lite.
"""
import sys
import os
import time
import json
import urllib.request
import urllib.error

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from traceops.circuit_breaker import CircuitBreaker, CircuitBreakerError
from traceops.otel_exporter import TraceOpsOtelEmitter
from traceops.async_judge import AsyncJudge

FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

# Configure Streamlit Page
st.set_page_config(
    page_title="TraceOps AI | Circuit-Breaker HUD",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Clean Dark-Mode Styling
st.markdown("""
<style>
    .stApp {
        background-color: #090d16;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .metric-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 12px 14px;
        text-align: center;
        transition: border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #374151;
    }
    .metric-val {
        font-size: 24px;
        font-weight: 700;
        margin-top: 2px;
        font-family: 'Cascadia Code', 'Consolas', monospace;
    }
    .metric-lbl {
        font-size: 11px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }
    .status-allow { color: #10b981; }
    .status-warn { color: #f59e0b; }
    .status-suspend_hitl { color: #f43f5e; }
    .status-halt { color: #ef4444; }
    .badge-latency { color: #38bdf8; }
    .badge-usd { color: #c084fc; }
    .hitl-box {
        background-color: rgba(244, 63, 94, 0.08);
        border: 1px solid #f43f5e;
        border-radius: 8px;
        padding: 14px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# State Management
if "breaker" not in st.session_state:
    st.session_state.breaker = CircuitBreaker(mode="enforce")
if "recent_events" not in st.session_state:
    st.session_state.recent_events = []
if "usd_saved" not in st.session_state:
    st.session_state.usd_saved = 0.0
if "last_status" not in st.session_state:
    st.session_state.last_status = "ALLOW"
if "last_latency" not in st.session_state:
    st.session_state.last_latency = 0.0
if "last_drift" not in st.session_state:
    st.session_state.last_drift = 0.0
if "last_reason" not in st.session_state:
    st.session_state.last_reason = "System idle. Fire an adversarial scenario or custom tool step below."
if "last_span" not in st.session_state:
    st.session_state.last_span = None
if "pending_hitl" not in st.session_state:
    st.session_state.pending_hitl = None

# Helper to check FastAPI proxy health
def check_fastapi_health() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(f"{FASTAPI_URL}/health", headers={"User-Agent": "TraceOps-Dashboard"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return True, f"ONLINE (Proxy: {data.get('mode', 'enforce').upper()})"
    except Exception:
        pass
    return False, "IN-PROCESS (Zero-Config Engine)"

fastapi_online, health_label = check_fastapi_health()

# Top Navigation Bar
h_col1, h_col2, h_col3 = st.columns([2.8, 1.2, 1.2])
with h_col1:
    st.markdown("### ⚡ **TraceOps AI** · Deterministic Circuit-Breaker")
    st.caption("Google DeepMind × Google Cloud Startup Buildathon India 2026 | Sub-15ms CPU Hot-Path Guard")

with h_col2:
    st.caption("Engine Runtime")
    if fastapi_online:
        st.success(f"🟢 {health_label}")
    else:
        st.info(f"⚡ {health_label}")

with h_col3:
    mode_toggle = st.radio(
        "Execution Mode",
        options=["ENFORCE", "SHADOW"],
        horizontal=True,
        index=0 if st.session_state.breaker.mode == "enforce" else 1,
        label_visibility="collapsed",
        help="ENFORCE halts rogue calls with HTTP 403; SHADOW logs violations & simulated dollar savings."
    )
    new_mode = "enforce" if mode_toggle == "ENFORCE" else "shadow"
    if st.session_state.breaker.mode != new_mode:
        st.session_state.breaker.set_mode(new_mode)
        try:
            req = urllib.request.Request(
                f"{FASTAPI_URL}/v1/mode?mode={new_mode}",
                data=b"",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=0.8)
        except Exception:
            pass
        st.toast(f"Mode switched to: {new_mode.upper()}", icon="🔄")

st.divider()

# Live KPI Strip
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-lbl">Circuit Decision</div>
        <div class="metric-val status-{st.session_state.last_status.lower()}">{st.session_state.last_status}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-lbl">Hot-Path Latency</div>
        <div class="metric-val badge-latency">{st.session_state.last_latency:.2f} ms</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-lbl">Cosine Drift Score</div>
        <div class="metric-val">{st.session_state.last_drift:.3f}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-lbl">Estimated USD Saved</div>
        <div class="metric-val badge-usd">${st.session_state.usd_saved:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-lbl">SLO Budget Headroom</div>
        <div class="metric-val" style="color: #10b981;">
            {max(0.0, 15.0 - st.session_state.last_latency):.1f} ms
        </div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Step Evaluation Engine (FastAPI Proxy first, graceful in-process fallback)
def dispatch_step_eval(tool_name: str, args: dict, context: str, scenario: str = "incident_triage", cost: float = 0.04):
    payload = {
        "tool_name": tool_name,
        "arguments": args,
        "step_cost_usd": cost,
        "step_tokens": 420,
        "step_context": context,
        "scenario": scenario,
        "mode": st.session_state.breaker.mode
    }

    if fastapi_online:
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{FASTAPI_URL}/v1/evaluate-step",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                record_event(tool_name, res)
                return
        except urllib.error.HTTPError as he:
            err_data = json.loads(he.read().decode("utf-8"))
            record_event(tool_name, err_data, halted=True)
            return
        except Exception:
            pass

    # In-Process Breaker Fallback
    try:
        res = st.session_state.breaker.evaluate_step(
            tool_name=tool_name,
            arguments=args,
            step_cost_usd=cost,
            step_tokens=420,
            step_context=context,
            scenario=scenario
        )
        record_event(tool_name, res)
    except CircuitBreakerError as e:
        record_event(tool_name, e.decision_record, halted=True)

def record_event(tool_name: str, res: dict, halted: bool = False):
    decision = res.get("decision", "HALT" if halted else "ALLOW")
    st.session_state.last_status = decision
    st.session_state.last_latency = float(res.get("latency_ms", 0.0))
    st.session_state.last_drift = float(res.get("drift_score", 0.0))
    st.session_state.last_reason = res.get("reason", "Action evaluated.")
    st.session_state.last_span = res.get("otel_span", {})
    st.session_state.usd_saved = float(res.get("total_simulated_usd_saved", st.session_state.usd_saved))

    if decision == "SUSPEND_HITL":
        st.session_state.pending_hitl = {
            "tool": tool_name,
            "args": res.get("otel_span", {}).get("arguments", {}),
            "reason": res.get("reason", "")
        }

    st.session_state.recent_events.insert(0, {
        "timestamp": time.strftime("%H:%M:%S"),
        "tool": tool_name,
        "decision": decision,
        "action": res.get("action_taken", "HALTED" if halted else "PROCEEDED"),
        "latency_ms": res.get("latency_ms", 0.0),
        "drift": res.get("drift_score", 0.0),
        "reason": res.get("reason", "")
    })

# Main Content Layout
col_left, col_right = st.columns([1.2, 1.8])

with col_left:
    st.markdown("#### 🎯 **1-Click Adversarial Scenarios**")
    st.caption("Fires live agent tool calls against the deterministic guard rails.")

    b1 = st.button("✅ 1. Normal Query (`ALLOW`, ~3 ms)", use_container_width=True)
    if b1:
        dispatch_step_eval(
            tool_name="refund_user",
            args={"user_id": "usr_99812", "amount": 45.00, "reason": "damaged_packaging"},
            context="process standard user refund within normal agent threshold",
            scenario="incident_triage"
        )
        st.rerun()

    b2 = st.button("🚨 2. Runaway Tool Loop (Tier-1 Catch <0.1 ms)", use_container_width=True)
    if b2:
        for _ in range(3):
            dispatch_step_eval(
                tool_name="fetch_pod_logs",
                args={"pod": "auth-service-v1", "tail": 100},
                context="investigate gke pod crash error logs for service telemetry",
                scenario="incident_triage"
            )
        st.rerun()

    b3 = st.button("🛑 3. Unauthorized Tool (`delete_production_db`)", use_container_width=True)
    if b3:
        dispatch_step_eval(
            tool_name="delete_production_db",
            args={"database": "payments_prod", "force": True},
            context="attempting to drop payments table to clear disk pressure",
            scenario="incident_triage"
        )
        st.rerun()

    b4 = st.button("⏸️ 4. High-Stakes Action ($2,500 Refund -> `SUSPEND_HITL`)", use_container_width=True)
    if b4:
        dispatch_step_eval(
            tool_name="refund_user",
            args={"user_id": "usr_vip_404", "amount": 2500.00, "reason": "sla_breach_claim"},
            context="issue major financial settlement exceeding single-agent autonomy limit",
            scenario="incident_triage"
        )
        st.rerun()

    # Interactive Human-in-the-Loop Sign-off Dialog
    if st.session_state.pending_hitl:
        st.markdown(f"""
        <div class="hitl-box">
            <b>⚠️ Human-in-the-Loop Approval Required</b><br>
            <small><b>Action:</b> <code>{st.session_state.pending_hitl['tool']}</code></small><br>
            <small><b>Audit:</b> {st.session_state.pending_hitl['reason']}</small>
        </div>
        """, unsafe_allow_html=True)
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            if st.button("👍 Approve", use_container_width=True):
                st.session_state.pending_hitl = None
                st.session_state.last_status = "ALLOW"
                st.session_state.last_reason = "Human Operator APPROVED high-stakes operation."
                st.toast("Action APPROVED by Human Operator", icon="✅")
                st.rerun()
        with h_col2:
            if st.button("🚫 Reject", use_container_width=True):
                st.session_state.pending_hitl = None
                st.session_state.last_status = "HALT"
                st.session_state.last_reason = "Human Operator REJECTED high-stakes operation."
                st.toast("Action REJECTED by Human Operator", icon="🛑")
                st.rerun()

    # Custom Tool Evaluator for Judges & Users
    with st.expander("🛠️ Test Custom Tool Step"):
        custom_tool = st.text_input("Tool Name", value="query_gke_telemetry")
        custom_args_raw = st.text_area("Arguments (JSON)", value='{"query": "cpu_utilization"}', height=70)
        custom_ctx = st.text_input("Context / Goal", value="Monitor cluster health during peak load")
        if st.button("Evaluate Custom Step", use_container_width=True):
            try:
                parsed_args = json.loads(custom_args_raw)
                dispatch_step_eval(tool_name=custom_tool, args=parsed_args, context=custom_ctx)
                st.rerun()
            except json.JSONDecodeError as je:
                st.error(f"Invalid JSON in arguments: {je}")

    st.write("")
    if st.button("🔄 Reset Circuit Breaker State", use_container_width=True):
        st.session_state.breaker.reset_trace()
        st.session_state.breaker.total_simulated_usd_saved = 0.0
        st.session_state.recent_events.clear()
        st.session_state.usd_saved = 0.0
        st.session_state.last_status = "ALLOW"
        st.session_state.last_latency = 0.0
        st.session_state.last_drift = 0.0
        st.session_state.last_reason = "Circuit breaker reset to fresh state."
        st.session_state.last_span = None
        st.session_state.pending_hitl = None
        TraceOpsOtelEmitter.get_instance().clear()
        try:
            req = urllib.request.Request(f"{FASTAPI_URL}/v1/reset", data=b"", method="POST")
            urllib.request.urlopen(req, timeout=0.8)
        except Exception:
            pass
        st.rerun()

with col_right:
    st.markdown("#### 📡 **Live Telemetry & Diagnostics**")
    st.markdown(f"**Latest Decision:** *{st.session_state.last_reason}*")

    if st.session_state.recent_events:
        st.dataframe(
            st.session_state.recent_events[:10],
            use_container_width=True,
            column_config={
                "timestamp": st.column_config.TextColumn("Time"),
                "tool": st.column_config.TextColumn("Tool"),
                "decision": st.column_config.TextColumn("Decision"),
                "action": st.column_config.TextColumn("Action"),
                "latency_ms": st.column_config.NumberColumn("Latency (ms)", format="%.2f"),
                "drift": st.column_config.NumberColumn("Drift", format="%.3f"),
            }
        )
    else:
        st.info("No telemetry events recorded yet. Click a scenario on the left to fire live events.")

    # OTel Span JSON inspector
    if st.session_state.last_span:
        with st.expander("🔍 Latest OpenTelemetry Span Payload"):
            st.json(st.session_state.last_span)

    # Architectural Proof
    with st.expander("🔬 Google Cloud & DeepMind Architecture Invariants"):
        st.markdown("""
        - **Invariant**: *"LLMs advise. The deterministic state machine decides."* Zero LLMs on hot path.
        - **Tier-1**: Exact duplicate hash detector (`< 0.1 ms`), least-privilege allowlist, token/USD budget ceilings.
        - **Tier-2**: In-process cosine distance against preloaded pgvector centroids (`< 2.0 ms`).
        - **Tier-3**: Pure deterministic LangGraph arbiter (`ALLOW`, `WARN`, `SUSPEND_HITL`, `HALT`).
        - **Async Judge**: OpenTelemetry spans scored off critical path by `gemini-3.5-flash-lite` (0 ms user latency).
        - **Offline Builder**: Trajectory baselines synthesized via `gemini-3.8-flash`.
        """)
