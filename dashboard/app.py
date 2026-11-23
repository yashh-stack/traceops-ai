"""
TraceOps AI: Live Jury Control Room.
Dark-mode, 1-screen live dashboard built for the 3-minute jury pitch
at Google DeepMind x Cloud Startup Buildathon India 2026.

Features:
- Live Execution Mode Switch: SHADOW vs ENFORCE
- Real-time FastAPI Proxy Health Badge (http://127.0.0.1:8000/health)
- 4 One-Click Live Adversarial Triggers hitting the real FastAPI POST /v1/evaluate-step endpoint:
  1. Normal Refund Query (ALLOW, ~6-7 ms)
  2. Runaway Recursive Tool Loop (Tier 1 hash catch, <0.5 ms, HALT in ENFORCE / logged savings in SHADOW)
  3. Unauthorized Tool Injection (delete_production_db) (Tier 1 allowlist block, <0.5 ms)
  4. Semantic Policy Drift / High-Value Refund ($2,500.00 -> SUSPEND_HITL with Approve/Reject actions)
- Live KPI Strip: Hot-Path Latency, Decision (ALLOW/WARN/SUSPEND_HITL/HALT), Cosine Drift, Estimated USD Saved,
  and Async OTel Span + Gemini Flash Judge Feed (0 ms hot-path overhead).
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
    page_title="TraceOps AI | Jury Control Room",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Dark Modern Styling
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }
    .metric-val {
        font-size: 26px;
        font-weight: 800;
        margin-top: 4px;
    }
    .metric-lbl {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .status-allow { color: #10b981; }
    .status-warn { color: #f59e0b; }
    .status-suspend_hitl { color: #ec4899; }
    .status-halt { color: #ef4444; }
    .badge-latency { color: #38bdf8; }
    .badge-usd { color: #a855f7; }
    .badge-hitl {
        background-color: #831843;
        color: #fbcfe8;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: bold;
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
    st.session_state.last_reason = "System ready. Click an adversarial trigger or send requests."
if "pending_hitl" not in st.session_state:
    st.session_state.pending_hitl = None

# Helper to check FastAPI proxy health
def check_fastapi_health() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(f"{FASTAPI_URL}/health", headers={"User-Agent": "TraceOps-Dashboard"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return True, f"ONLINE (v1.0.0, {data.get('mode', 'enforce').upper()})"
    except Exception:
        pass
    return False, "OFFLINE (Using In-Process Breaker Fallback)"

fastapi_online, health_label = check_fastapi_health()

# Top Header Bar
col_h1, col_h2, col_h3 = st.columns([2.5, 1.2, 1.3])
with col_h1:
    st.title("⚡ TraceOps AI: Deterministic Agent Circuit-Breaker")
    st.caption("Google DeepMind x Cloud Startup Buildathon India 2026 | Hot-Path Guard (<15 ms) & Runtime Evals Engine")

with col_h2:
    st.write("**FastAPI Proxy:**")
    if fastapi_online:
        st.success(f"🟢 {health_label}")
    else:
        st.warning(f"🟡 {health_label}")

with col_h3:
    mode_toggle = st.radio(
        "**Execution Mode:**",
        options=["ENFORCE", "SHADOW"],
        horizontal=True,
        index=0 if st.session_state.breaker.mode == "enforce" else 1,
        help="ENFORCE halts rogue calls; SHADOW logs violations & simulated dollar savings without blocking."
    )
    new_mode = "enforce" if mode_toggle == "ENFORCE" else "shadow"
    if st.session_state.breaker.mode != new_mode:
        st.session_state.breaker.set_mode(new_mode)
        # Also sync remote FastAPI if online
        try:
            req = urllib.request.Request(
                f"{FASTAPI_URL}/v1/mode?mode={new_mode}",
                data=b"",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=1.0)
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
        <div class="metric-lbl">Active Mode</div>
        <div class="metric-val" style="color: {'#3b82f6' if st.session_state.breaker.mode == 'enforce' else '#eab308'};">
            {st.session_state.breaker.mode.upper()}
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

    # 1. Try FastAPI Proxy endpoint
    if fastapi_online:
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{FASTAPI_URL}/v1/evaluate-step",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                record_event(tool_name, res)
                return
        except urllib.error.HTTPError as he:
            # 403 Forbidden is ENFORCE HALT
            err_data = json.loads(he.read().decode("utf-8"))
            record_event(tool_name, err_data, halted=True)
            return
        except Exception:
            pass

    # 2. In-Process Breaker Fallback
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

# Main Layout
col_left, col_right = st.columns([1.3, 1.7])

with col_left:
    st.subheader("🎯 1-Click Live Adversarial Scenarios")
    st.caption("Fires live requests against POST /v1/evaluate-step with zero hot-path LLM overhead.")

    # Trigger 1: Normal Refund Query
    b1 = st.button("✅ 1. Normal Refund Query (ALLOW, ~6–7 ms)", use_container_width=True)
    if b1:
        dispatch_step_eval(
            tool_name="refund_user",
            args={"user_id": "usr_99812", "amount": 45.00, "reason": "damaged_packaging"},
            context="process standard user refund within normal agent threshold",
            scenario="incident_triage"
        )
        st.rerun()

    # Trigger 2: Runaway Recursive Loop
    b2 = st.button("🚨 2. Runaway Recursive Loop (Exact Hash <0.5 ms)", use_container_width=True)
    if b2:
        st.info("Simulating 3 identical recursive tool calls...")
        for _ in range(3):
            dispatch_step_eval(
                tool_name="fetch_pod_logs",
                args={"pod": "auth-service-v1", "tail": 100},
                context="investigate gke pod crash error logs for service telemetry",
                scenario="incident_triage"
            )
        st.rerun()

    # Trigger 3: Unauthorized Tool Injection
    b3 = st.button("🛑 3. Unauthorized Tool Injection (delete_production_db)", use_container_width=True)
    if b3:
        dispatch_step_eval(
            tool_name="delete_production_db",
            args={"database": "payments_prod", "force": True},
            context="attempting to drop payments table to clear disk pressure",
            scenario="incident_triage"
        )
        st.rerun()

    # Trigger 4: High-Value Refund HITL Suspend
    b4 = st.button("⏸️ 4. High-Value Refund ($2,500.00 -> SUSPEND_HITL)", use_container_width=True)
    if b4:
        dispatch_step_eval(
            tool_name="refund_user",
            args={"user_id": "usr_vip_404", "amount": 2500.00, "reason": "sla_breach_claim"},
            context="issue major financial settlement exceeding single-agent autonomy limit",
            scenario="incident_triage"
        )
        st.rerun()

    # Interactive Human-in-the-Loop Dialog if suspended
    if st.session_state.pending_hitl:
        st.warning(f"⚠️ **Human-in-the-Loop Sign-Off Required**")
        st.write(f"**Tool:** `{st.session_state.pending_hitl['tool']}`")
        st.write(f"**Rationale:** {st.session_state.pending_hitl['reason']}")
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            if st.button("👍 Approve Action", use_container_width=True):
                st.session_state.pending_hitl = None
                st.session_state.last_status = "ALLOW"
                st.session_state.last_reason = "Human Supervisor explicitly APPROVED high-stakes action."
                st.toast("Action APPROVED by Human Operator", icon="✅")
                st.rerun()
        with h_col2:
            if st.button("🚫 Reject Action", use_container_width=True):
                st.session_state.pending_hitl = None
                st.session_state.last_status = "HALT"
                st.session_state.last_reason = "Human Supervisor explicitly REJECTED high-stakes action."
                st.toast("Action REJECTED by Human Operator", icon="🛑")
                st.rerun()

    st.write("")
    if st.button("🔄 Reset Circuit Breaker State & History", use_container_width=True):
        st.session_state.breaker.reset_trace()
        st.session_state.breaker.total_simulated_usd_saved = 0.0
        st.session_state.recent_events.clear()
        st.session_state.usd_saved = 0.0
        st.session_state.last_status = "ALLOW"
        st.session_state.last_latency = 0.0
        st.session_state.last_drift = 0.0
        st.session_state.last_reason = "Circuit breaker reset to fresh state."
        st.session_state.pending_hitl = None
        TraceOpsOtelEmitter.get_instance().clear()
        try:
            req = urllib.request.Request(f"{FASTAPI_URL}/v1/reset", data=b"", method="POST")
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass
        st.rerun()

with col_right:
    st.subheader("📡 Live OpenTelemetry Span Feed & Diagnostics")
    st.markdown(f"**Latest Decision Reason:** *{st.session_state.last_reason}*")

    if st.session_state.recent_events:
        st.dataframe(
            st.session_state.recent_events[:12],
            use_container_width=True,
            column_config={
                "decision": st.column_config.TextColumn("Decision"),
                "action": st.column_config.TextColumn("Action"),
                "latency_ms": st.column_config.NumberColumn("Latency (ms)", format="%.2f"),
                "drift": st.column_config.NumberColumn("Drift", format="%.3f"),
            }
        )
    else:
        st.info("No telemetry spans logged yet. Click one of the 4 triggers on the left to fire live events.")

    # Google AI Stack & Architectural Proof Card
    with st.expander("🔬 Google Cloud & DeepMind Architecture Invariants"):
        st.markdown("""
        - **Invariant 1**: *"LLMs advise. The deterministic state machine decides."* Zero LLM calls on hot path.
        - **Tier-1 Guard**: Exact duplicate hash detector (`< 0.5 ms`), allowlist boundaries, and hard USD/token ceilings.
        - **Tier-2 Scorer**: In-process cosine distance against preloaded golden centroids (`< 2.0 ms`).
        - **Tier-3 State Machine**: Pure deterministic LangGraph arbiter (`ALLOW`, `WARN`, `SUSPEND_HITL`, `HALT`).
        - **Async Judge**: Background OpenTelemetry spans evaluated by `gemini-3.5-flash-lite` (0 ms critical path overhead).
        - **Offline Baseline**: Trajectory synthesis & pgvector centroids powered by `gemini-3.8-flash`.
        """)
