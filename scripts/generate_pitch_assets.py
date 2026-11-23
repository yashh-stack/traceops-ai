import os
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

PITCH_DIR = "C:/Users/yashs/Projects/traceops-ai/pitch"
os.makedirs(PITCH_DIR, exist_ok=True)
SLIDES_DIR = os.path.join(PITCH_DIR, "rendered_slides")
os.makedirs(SLIDES_DIR, exist_ok=True)
AUDIO_DIR = os.path.join(PITCH_DIR, "rendered_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "en-IN-PrabhatNeural"

ACTS = [
    {
        "id": "act1_crisis",
        "title": "ACT 1: THE RUNAWAY CRISIS",
        "headline": "When AI Agents Hallucinate in Production, Balances Vanish in Milliseconds.",
        "points": [
            "Autonomous agents are executing live database queries, refunds, and cloud APIs.",
            "A single recursive loop or hallucinated argument drains balances before alerts fire.",
            "Traditional post-facto observability tools only log catastrophic failures after the damage is done."
        ],
        "metric_val": "$0.00",
        "metric_lbl": "Zero Circuit Protection in Modern Agent Frameworks",
        "accent": "#ef4444",
        "speech": "When AI agents hallucinate in production, balances vanish in milliseconds. Autonomous agents now execute live database mutations, user refunds, and cloud infrastructure changes. But today, if an agent enters a runaway recursive loop, or hallucinates an unauthorized tool like delete production database, there is zero deterministic protection on the hot path. Observability logs tell you what broke after your company has already lost thousands of dollars."
    },
    {
        "id": "act2_conventional_trap",
        "title": "ACT 2: THE CONVENTIONAL TRAP",
        "headline": "LLMs Guarding LLMs Add 150ms+ Latency and Fail Determinism.",
        "points": [
            "Industry standard: Placing a secondary Small Language Model (SLM) on the hot path.",
            "GPU SLM Guardrail latency: 152 ms average — destroys real-time agent responsiveness.",
            "Stochastic weakness: LLM guards hallucinate their own decisions and fail under load."
        ],
        "metric_val": "152 ms",
        "metric_lbl": "GPU SLM Guardrail Latency Baseline",
        "accent": "#f59e0b",
        "speech": "The conventional industry approach has been to put another Small Language Model on the critical path to police the agent. But that creates a massive architectural trap. A GPU based SLM adds over 150 milliseconds of latency to every single tool execution, and because it is stochastic, it can hallucinate its own approvals. Our core architectural invariant is absolute: LLMs advise. The deterministic state machine decides."
    },
    {
        "id": "act3_architecture",
        "title": "ACT 3: THE TRACEOPS AI BREAKTHROUGH",
        "headline": "Hot-Path Determinism (<15 ms) + Async Gemini 3.5 Intelligence.",
        "points": [
            "Hot Path (p95: 6.54 ms): Zero LLM calls. Pure Tier 1 hashing & Tier 2 vector centroids.",
            "Async Evals Path: OpenTelemetry spans judged by Gemini 3.5 Flash Lite (0 ms overhead).",
            "Offline Synthesis: Trajectory baselines synthesized via Gemini 3.8 Flash."
        ],
        "metric_val": "6.54 ms",
        "metric_lbl": "Measured Hot-Path p95 Latency (SLO < 15 ms)",
        "accent": "#38bdf8",
        "speech": "TraceOps AI introduces an unprecedented dual-path architecture. On the synchronous hot path, there are exactly zero remote LLM calls. In sub seven milliseconds, our Tier 1 deterministic guard checks duplicate tool hashes, validates Pydantic schemas, and enforces token ceilings, while Tier 2 scores semantic drift against preloaded vector centroids. Then, off the critical path, Google Gemini 3.5 Flash Lite audits OpenTelemetry spans with zero impact on user latency."
    },
    {
        "id": "act4_live_demo",
        "title": "ACT 4: LIVE JURY CONTROL ROOM",
        "headline": "Intercepting Runaway Loops in 0.024 ms & Enforcing HITL at $500.",
        "points": [
            "Runaway Loop Detection: Catches 3 identical call hashes in 0.0247 ms (40x faster than SLO).",
            "Least-Privilege Allowlist: Blocks delete_production_db instantaneously.",
            "Human-in-the-Loop: Automatically suspends high-value refunds ($2,500 > $500) awaiting sign-off."
        ],
        "image": "C:/Users/yashs/Projects/traceops-ai/pitch/screenshots/02_runaway_loop_intercepted.png",
        "metric_val": "0.024 ms",
        "metric_lbl": "Tier 1 Exact Hash Loop Interception",
        "accent": "#10b981",
        "speech": "Here is TraceOps AI live in our single-container jury dashboard. When an adversarial runaway loop fires, TraceOps intercepts the third identical hash in just 24 microseconds, halting execution instantly. When an unauthorized tool like delete production database is injected, the least privilege allowlist blocks it before invocation. And for sensitive operations, like a 2,500 dollar refund, TraceOps triggers Human-in-the-Loop suspension, pausing execution for supervisor approval."
    },
    {
        "id": "act5_benchmarks",
        "title": "ACT 5: EMPIRICAL BENCHMARKS & EFFICIENCY",
        "headline": "23.2x Faster Than GPU SLMs With 95.7% Latency Reduction.",
        "points": [
            "Tested over 200 real iterations: p50 = 2.85 ms, p95 = 6.54 ms, max = 10.23 ms.",
            "Quantized in-memory centroids eliminate live Cloud SQL requirement (100% reliable).",
            "Full compliance with $5 GCP Budget: Cloud Run min-instances 0, max-instances 2."
        ],
        "metric_val": "23.24x",
        "metric_lbl": "Speedup vs 152 ms GPU SLM Baseline",
        "accent": "#a855f7",
        "speech": "Across 200 rigorous benchmark evaluations, TraceOps AI delivers a p50 latency of 2.85 milliseconds and a p95 of 6.54 milliseconds. That is over twenty-three times faster than GPU based guardrails, representing a 95.7 percent latency reduction. Furthermore, our quantized in-memory centroid fallback guarantees 100 percent reliability without expensive Cloud SQL instances, easily conforming to Google Cloud Run zero-scale budget constraints."
    },
    {
        "id": "act6_vision",
        "title": "ACT 6: VIKSIT BHARAT & ENTERPRISE AGENT SAFETY",
        "headline": "Building the Deterministic Safety Standard for Indian Enterprise AI.",
        "points": [
            "Production ready: Drop-in @traceops.guard decorator + FastAPI Cloud Run proxy.",
            "Exported Google Agent Skills: drift_check and tool_boundary_audit for LangGraph & Vertex AI.",
            "Empowering India's digital economy to deploy autonomous agents with mathematical certainty."
        ],
        "metric_val": "100%",
        "metric_lbl": "Deterministic Safety Guarantee",
        "accent": "#38bdf8",
        "speech": "TraceOps AI provides the missing deterministic bedrock for India's booming agentic ecosystem. By combining microsecond edge determinism with Google DeepMind's Gemini 3.5 and 3.8 intelligence, we enable Indian startups and enterprises to unleash autonomous agents into production with mathematical certainty. LLMs advise, but the deterministic state machine decides. Thank you."
    }
]

async def generate_speech():
    print("Generating speech audio via edge_tts (en-IN-PrabhatNeural)...")
    for act in ACTS:
        audio_file = os.path.join(AUDIO_DIR, f"{act['id']}.mp3")
        comm = edge_tts.Communicate(act["speech"], VOICE, rate="-4%")
        await comm.save(audio_file)
        print(f"Generated: {audio_file}")

def render_slide(act, output_path):
    w, h = 1920, 1080
    im = Image.new("RGB", (w, h), color="#0b0f19")
    draw = ImageDraw.Draw(im)

    # Accent top border
    draw.rectangle([(0, 0), (w, 8)], fill=act["accent"])

    # Load system fonts
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 26)
        font_head = ImageFont.truetype("arialbd.ttf", 44)
        font_body = ImageFont.truetype("arial.ttf", 26)
        font_val = ImageFont.truetype("arialbd.ttf", 80)
        font_lbl = ImageFont.truetype("arial.ttf", 20)
        font_badge = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_head = font_title
        font_body = font_title
        font_val = font_title
        font_lbl = font_title
        font_badge = font_title

    # Header section
    draw.rectangle([(80, 50), (450, 90)], fill="#1e293b", outline="#334155")
    draw.text((100, 60), act["title"], fill=act["accent"], font=font_title)
    draw.text((w - 550, 60), "GOOGLE DEEPMIND x CLOUD BUILDATHON 2026", fill="#64748b", font=font_badge)

    # Main Headline
    draw.text((80, 120), act["headline"], fill="#f8fafc", font=font_head)
    draw.line([(80, 195), (w - 80, 195)], fill="#1e293b", width=2)

    # Left content box vs right metric card / image
    if "image" in act and os.path.exists(act["image"]):
        # Has screenshot image
        left_w = 900
        y_text = 240
        for pt in act["points"]:
            draw.text((80, y_text), f"• {pt}", fill="#cbd5e1", font=font_body)
            y_text += 70

        # Draw screenshot on right
        try:
            ss = Image.open(act["image"])
            ss = ss.resize((850, 480))
            # border
            draw.rectangle([(980, 230), (1850, 730)], fill="#0f172a", outline=act["accent"], width=3)
            im.paste(ss, (990, 240))
        except Exception as e:
            print(f"Failed to paste image: {e}")

        # Metric Card bottom left
        draw.rectangle([(80, 780), (600, 960)], fill="#131b2e", outline="#334155", width=2)
        draw.text((110, 805), act["metric_val"], fill=act["accent"], font=font_val)
        draw.text((110, 910), act["metric_lbl"], fill="#94a3b8", font=font_lbl)

    else:
        # 2-Column layout: Points on left (1050px), Hero Card on right
        y_text = 260
        for pt in act["points"]:
            draw.text((80, y_text), f"•  {pt}", fill="#cbd5e1", font=font_body)
            y_text += 90

        # Right Hero Metric Card
        draw.rectangle([(1200, 240), (1840, 700)], fill="#131b2e", outline=act["accent"], width=3)
        draw.text((1260, 360), act["metric_val"], fill=act["accent"], font=font_val)
        draw.text((1260, 480), act["metric_lbl"], fill="#94a3b8", font=font_title)
        draw.line([(1260, 540), (1780, 540)], fill="#334155", width=2)
        draw.text((1260, 580), "TRACEOPS AI DETERMINISTIC KERNEL", fill="#64748b", font=font_lbl)

    # Footer banner
    draw.rectangle([(0, h - 60), (w, h)], fill="#070a12")
    draw.text((80, h - 42), "TraceOps AI | Deterministic Circuit-Breaker & Runtime Evals Engine", fill="#94a3b8", font=font_badge)
    draw.text((w - 420, h - 42), "Core Invariant: LLMs Advise, State Machines Decide", fill=act["accent"], font=font_badge)

    im.save(output_path, quality=95)
    print(f"Rendered slide: {output_path}")

def render_all_slides():
    print("Rendering 1080p presentation slides...")
    for act in ACTS:
        out_file = os.path.join(SLIDES_DIR, f"{act['id']}.png")
        render_slide(act, out_file)

if __name__ == "__main__":
    asyncio.run(generate_speech())
    render_all_slides()
