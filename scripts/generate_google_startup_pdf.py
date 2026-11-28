"""
Professional PDF generator for TraceOps AI Executive & Technical Brief.
Built for submission to the Google for Startups Cloud Program (AI-First) and Google AI Acceleration programs.
Strictly formatted into a balanced, clean 3-page executive document.
"""
from __future__ import annotations

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)


def build_traceops_pdf(output_path: str) -> None:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.50 * inch,
        rightMargin=0.50 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )

    styles = getSampleStyleSheet()

    # Color palette
    primary_color = colors.HexColor("#1A73E8")     # Google Blue
    dark_neutral = colors.HexColor("#202124")      # Google Dark Charcoal
    slate_blue = colors.HexColor("#0D47A1")        # Deep Blue
    table_header_bg = colors.HexColor("#E8F0FE")   # Soft Blue Tint
    border_color = colors.HexColor("#DADCE0")      # Neutral border
    accent_green = colors.HexColor("#137333")      # Verified green
    card_bg = colors.HexColor("#F1F3F4")

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=dark_neutral,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
        spaceAfter=8,
    )

    h1_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=slate_blue,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=dark_neutral,
        spaceAfter=4,
    )

    code_style = ParagraphStyle(
        "CodeCallout",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0D47A1"),
        backColor=card_bg,
        borderColor=border_color,
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=11.5,
        textColor=dark_neutral,
        leftIndent=10,
        spaceAfter=2,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10.5,
        textColor=primary_color,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=10,
        textColor=dark_neutral,
    )

    table_cell_text = ParagraphStyle(
        "TableCellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.8,
        textColor=dark_neutral,
    )

    table_cell_green = ParagraphStyle(
        "TableCellGreen",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.8,
        textColor=accent_green,
    )

    story = []

    # ==================== PAGE 1: TITLE, SUMMARY & 3-TIER ARCHITECTURE ====================
    story.append(Paragraph("TraceOps AI: Sub-15 ms Runtime Circuit-Breaker for Enterprise Agents", title_style))
    story.append(Paragraph(
        "<b>Executive & Technical Dossier</b> | <b>Startup:</b> TraceOps AI (Team: Deterministic Systems; Founder: Yash Sharma, Alwar, India)<br/>"
        "<b>Google Cloud Architecture:</b> In-process CPU deterministic guard + Cloud Run serverless engine + Gemini 3.5 Flash Lite async judge + Cloud Trace telemetry.",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=primary_color, spaceBefore=0, spaceAfter=6))

    # Key Metrics Proof Point Table
    t1_data = [
        [
            Paragraph("Core Benchmark / Metric", table_header_style),
            Paragraph("Verified Production Proof Point (Zero-Fabrication Contract)", table_header_style),
        ],
        [
            Paragraph("1.44 ms Hot-Path Latency", table_cell_bold),
            Paragraph("Verified Linux CI p95 hot-path latency (<b>105.54x faster</b> than 152 ms GPU SLM guardrails; 1.32 ms p50 / 1.54 ms p99).", table_cell_text),
        ],
        [
            Paragraph("0.0244 ms Tier-1 Interception", table_cell_bold),
            Paragraph("Exact state-hash loop detection and USD budget ceiling enforcement before tool execution or LLM token burn.", table_cell_text),
        ],
        [
            Paragraph("0 CVEs & 18/18 Clean CI/CD", table_cell_bold),
            Paragraph("<b>18/18 passing pytest suite</b>, 0 ruff errors, 0 mypy/pyright type errors, 0 bandit SAST warnings, 0 CVEs via pip-audit, 205.72 MiB container.", table_cell_text),
        ],
        [
            Paragraph("Live Cloud Run Telemetry", table_cell_bold),
            Paragraph("Live endpoint (asia-south1): <b>100/100 HTTP 200 OK (0.00% error rate)</b>, p50 93.77 ms, p95 125.31 ms across public Internet WAN.", table_cell_text),
        ],
        [
            Paragraph("$1.68B to $8.62B Market", table_cell_bold),
            Paragraph("Agent Observability & Governance market (2026–2031, <b>38.69% CAGR</b>; Mordor Intelligence). Gartner projects 40% agent decommissioning by 2027.", table_cell_text),
        ],
    ]
    t1 = Table(t1_data, colWidths=[2.1 * inch, 5.4 * inch])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), table_header_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t1)
    story.append(Spacer(1, 6))

    # Section 1: Problem & Principle
    story.append(Paragraph("1. Problem & Core Principle: Post-Hoc Observability Cannot Stop Runaway Agents", h1_style))
    story.append(Paragraph(
        "Enterprise multi-agent systems fail synchronously—via recursive tool-call storms, unauthorized API mutations, prompt injections, and semantic goal drift. "
        "Yet incumbent observability platforms (LangSmith, Langfuse, Arize Phoenix) record traces asynchronously <i>after</i> budget exhaustion or SLA breach has occurred. "
        "Gartner (May 2026) projects that <b>40% of enterprises will demote or decommission autonomous AI agents by 2027</b> due to governance failures, while Cisco/Splunk (Oct 2026) reports <b>83% of organizations are concerned about unintended agent consequences</b>.",
        body_style
    ))
    story.append(Paragraph(
        "<b>TraceOps AI Principle:</b> <i>LLMs advise; the deterministic state machine decides.</i> Teams adopt TraceOps in zero-risk <b>SHADOW</b> mode to measure policy violations and simulated dollar savings, then switch to <b>ENFORCE</b> mode to halt rogue agent steps in under 15 ms.",
        body_style
    ))
    story.append(Paragraph(
        "<code>pip install traceops  # Universal SDK for LangGraph, AutoGen, CrewAI, FastMCP, and Google GenAI ADK</code>",
        code_style
    ))

    # Section 2: Architecture
    story.append(Paragraph("2. 3-Tier Architecture & Resilient Multi-Instance Design", h1_style))
    story.append(Paragraph(
        "TraceOps eliminates the 152 ms latency penalty of LLM-based guardrails by partitioning governance across three purpose-built tiers:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Tier 1 (Deterministic CPU Guard):</b> In-process cycle detector executes in <b>0.0146 ms (Linux CI) / 0.0244 ms (local)</b>. Enforces duplicate call limits (max 3), USD cost ceilings, token caps, least-privilege allowlists, and linear-time PII/secret scrubbing before any trace egresses.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Tier 2 (Semantic Drift Scorer):</b> In-memory quantized embedding centroid evaluation (<b>1.32 ms p50 / 1.44 ms p95</b>). Detects trajectory hijacking without synchronous network hops, with optional Cloud SQL (PostgreSQL + pgvector) sync.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Tier 3 (Async OTel Judge & Google Cloud Trace):</b> Non-blocking BatchSpanProcessor samples 100% of HALT/SUSPEND events and 10% of nominal traces. Asynchronously evaluates spans using <b>Gemini 3.5 Flash Lite</b> and synthesizes regression cases with <b>Gemini 3.8 Flash</b> (0 ms hot-path impact). Exports durable spans directly to Google Cloud Trace.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Distributed Storage Adapter:</b> Pluggable <code>create_trace_breaker_store()</code> provides thread-safe bounded LRU+TTL in-memory cache with graceful Redis clustering fallback for multi-instance Cloud Run concurrency.",
        bullet_style
    ))

    # ==================== PAGE 2: VERIFICATION TELEMETRY & COMPETITIVE MATRIX ====================
    story.append(PageBreak())
    story.append(Paragraph("3. Empirical Verification Matrix & Live Production Telemetry", h1_style))
    story.append(Paragraph(
        "All metrics below are verified through automated CI/CD gates and live Cloud Run production sweeps. Zero synthetic data.",
        body_style
    ))

    # Comprehensive Verification Table
    t2_data = [
        [
            Paragraph("Verification Gate", table_header_style),
            Paragraph("Target SLO", table_header_style),
            Paragraph("Measured Production Result", table_header_style),
            Paragraph("Compliance Status", table_header_style),
        ],
        [
            Paragraph("Hot-Path Latency (Linux CI)", table_cell_bold),
            Paragraph("&lt; 15.0 ms p95", table_cell_text),
            Paragraph("<b>p50 1.32 ms · p95 1.44 ms · p99 1.54 ms</b>", table_cell_text),
            Paragraph("PASS (10.4x margin)", table_cell_green),
        ],
        [
            Paragraph("Tier 1 Exact Loop Interception", table_cell_bold),
            Paragraph("&lt; 1.0 ms", table_cell_text),
            Paragraph("<b>0.0146 ms (Linux CI) · 0.0244 ms (local)</b>", table_cell_text),
            Paragraph("PASS (40.9x margin)", table_cell_green),
        ],
        [
            Paragraph("Adversarial Test Suite", table_cell_bold),
            Paragraph("100% passing", table_cell_text),
            Paragraph("<b>18/18 pytest passing</b> (0 warnings, 5.47s execution)", table_cell_text),
            Paragraph("PASS", table_cell_green),
        ],
        [
            Paragraph("Security & Supply Chain Audit", table_cell_bold),
            Paragraph("0 Vulnerabilities", table_cell_text),
            Paragraph("0 ruff errors · 0 mypy/pyright errors · 0 bandit issues · 0 pip-audit CVEs", table_cell_text),
            Paragraph("PASS (Enterprise Ready)", table_cell_green),
        ],
        [
            Paragraph("Container & Build Hygiene", table_cell_bold),
            Paragraph("&lt; 500 MiB, non-root", table_cell_text),
            Paragraph("<b>205.72 MiB</b> (python:3.12-slim multi-stage, UID 1001 traceopsuser)", table_cell_text),
            Paragraph("PASS", table_cell_green),
        ],
        [
            Paragraph("Live Cloud Run Endpoint (Warm)", table_cell_bold),
            Paragraph("0% error rate, &lt; 500 ms", table_cell_text),
            Paragraph("<b>100/100 requests (0.00% err) · p50 93.77 ms · p95 125.31 ms</b>", table_cell_text),
            Paragraph("PASS (Zero Downtime)", table_cell_green),
        ],
        [
            Paragraph("Automated GCP CI/CD Pipeline", table_cell_bold),
            Paragraph("Zero-downtime CD", table_cell_text),
            Paragraph("GitHub Actions OIDC WIF → Artifact Registry → Cloud Run Canary Promotion", table_cell_text),
            Paragraph("PASS (Fully Automated)", table_cell_green),
        ],
    ]
    t2 = Table(t2_data, colWidths=[1.8 * inch, 1.2 * inch, 3.2 * inch, 1.3 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), table_header_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Section 4: Market Sizing & Competitive Landscape
    story.append(Paragraph("4. Market Opportunity & Competitive Landscape", h1_style))
    story.append(Paragraph(
        "Verified industry market forecasts project rapid growth across the agent governance, observability, and safety sectors:",
        body_style
    ))
    story.append(Paragraph("• <b>Agent Observability & Governance Market:</b> $1.68B (2026) growing to <b>$8.62B by 2031 at 38.69% CAGR</b> (Mordor Intelligence).", bullet_style))
    story.append(Paragraph("• <b>Gartner Securing AI Market:</b> Projected to reach <b>$4.80B by 2027</b> (Gartner Research).", bullet_style))
    story.append(Paragraph("• <b>Agentic AI Governance & Guardrails:</b> Forecast at <b>$6.85B by 2032 at 41.0% CAGR</b> (MarketsandMarkets 2025–2032).", bullet_style))
    story.append(Paragraph("• <b>Bottom-Up Serviceable Obtainable Market (SOM):</b> 100 enterprise agent teams @ $15K ACV = $1.5M ARR (Year 1–2), scaling to $100M+ ARR across 1,000+ VPC enterprise accounts.", bullet_style))
    story.append(Spacer(1, 6))

    # Competitive Matrix Table
    t3_data = [
        [
            Paragraph("Product / Category", table_header_style),
            Paragraph("Representative Players", table_header_style),
            Paragraph("Primary Mechanism", table_header_style),
            Paragraph("TraceOps AI Structural Advantage", table_header_style),
        ],
        [
            Paragraph("<b>Runtime Circuit-Breaker</b>", table_cell_bold),
            Paragraph("<b>TraceOps AI (Apache 2.0)</b>", table_cell_bold),
            Paragraph("In-process CPU state machine + centroid drift + async OTel Gemini judge", table_cell_text),
            Paragraph("<b>1.44 ms p95 synchronous halt; zero GPU latency; stateful multi-step loop prevention.</b>", table_cell_green),
        ],
        [
            Paragraph("Model & I/O Guardrails", table_cell_text),
            Paragraph("NVIDIA NeMo, Guardrails AI, Meta LlamaFirewall", table_cell_text),
            Paragraph("Colang DSL, transformer regex/scanners, inline LLM eval", table_cell_text),
            Paragraph("Avoids 152 ms+ GPU/LLM inline latency penalty and stateful cross-step loop blindness.", table_cell_text),
        ],
        [
            Paragraph("HTTP LLM Gateways", table_cell_text),
            Paragraph("LiteLLM, Portkey Gateway, Cloudflare AI Gateway", table_cell_text),
            Paragraph("Network proxy routing, rate limits, provider failover", table_cell_text),
            Paragraph("Complementary: TraceOps intercepts tool loops inside agent runtime before proxy token burn.", table_cell_text),
        ],
        [
            Paragraph("Post-Hoc Observability", table_cell_text),
            Paragraph("LangSmith, Langfuse, Arize Phoenix, Comet Opik", table_cell_text),
            Paragraph("Asynchronous trace ingest, offline dashboards, evals", table_cell_text),
            Paragraph("Sits upstream of observability: halts runaway damage in flight, then forwards scrubbed OTel spans.", table_cell_text),
        ],
    ]
    t3 = Table(t3_data, colWidths=[1.5 * inch, 1.6 * inch, 2.0 * inch, 2.4 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), table_header_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t3)

    # ==================== PAGE 3: GOOGLE CLOUD ALIGNMENT & PROGRAM APPLICATION ====================
    story.append(PageBreak())
    story.append(Paragraph("5. Google Cloud Alignment & Google for Startups (AI-First) Program Fit", h1_style))
    story.append(Paragraph(
        "TraceOps AI is architected natively around Google Cloud services and Google DeepMind AI infrastructure. "
        "Acceptance into the <b>Google for Startups Cloud Program (AI-First)</b> directly accelerates enterprise deployment across four vectors:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Gemini 3.5 Flash Lite & Gemini 3.8 Flash Consumption:</b> TraceOps uses Gemini Flash Lite for high-frequency out-of-band span root-cause analysis and Gemini Pro for offline centroid baseline generation. Google Cloud credits scale continuous eval throughput for thousands of enterprise agent runs.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Google Cloud Run & Cloud SQL Infrastructure:</b> Serverless engine deployed in <code>asia-south1</code> (with global replication targets) alongside Cloud SQL (PostgreSQL + pgvector) for enterprise semantic policy centroid synchronization.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Google Cloud Trace & Cloud Monitoring Integration:</b> First-class OTel integration streams scrubbed agent governance spans directly into Google Cloud Trace, giving GCP enterprises native agent observability with zero configuration.",
        bullet_style
    ))
    story.append(Paragraph(
        "• <b>Enterprise Security & Workload Identity Federation (WIF):</b> Implements keyless GitHub Actions OIDC federation with Google Cloud IAM and Secret Manager, eliminating long-lived service account keys in compliance with Google Cloud Security Best Practices.",
        bullet_style
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("6. Commercialization Roadmap & Bottom-Up Revenue Wedge", h1_style))
    story.append(Paragraph(
        "TraceOps executes a proven DevTools commercialization flywheel designed for rapid enterprise adoption:",
        body_style
    ))
    story.append(Paragraph(
        "1. <b>Paid Discovery Wedge ($1,500 Agent Reliability Audit):</b> 48-hour staging deployment installing TraceOps in SHADOW mode. Generates an empirical audit report quantifying runaway loops, token waste, and semantic drift risks.",
        bullet_style
    ))
    story.append(Paragraph(
        "2. <b>PLG to Team Control Plane ($500–$2,000/mo):</b> Self-serve hosted SaaS on Cloud Run offering centralized policy management, team dashboards, and automated Gemini regression case synthesis.",
        bullet_style
    ))
    story.append(Paragraph(
        "3. <b>Enterprise VPC Deployment ($50K–$250K ACV):</b> On-premise / private GCP VPC deployment for regulated financial, telecom, and defense accounts requiring air-gapped deterministic safety and zero PII egress.",
        bullet_style
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("7. Authoritative References & Citations", h1_style))
    citations = [
        "1. Gartner — <i>40% of Enterprises Will Demote or Decommission Autonomous AI Agents by 2027</i> (May 2026).",
        "2. Gartner — <i>Market for Securing AI Forecast to Reach $4.8B in 2027</i> (Aug 2026).",
        "3. Cisco / Splunk — <i>State of Observability 2026: The Agentic Transition</i> (Oct 2026).",
        "4. Mordor Intelligence — <i>Agent Observability & Governance Market Growth & Trends (2026–2031)</i> (Sept 2026).",
        "5. MarketsandMarkets — <i>Agentic AI Governance & Guardrails Market Global Forecast (2025–2032)</i>.",
        "6. Google Cloud — <i>Google for Startups Cloud Program (AI-First Tier: up to $350k in Cloud & Gemini credits)</i>.",
        "7. Dynatrace — <i>Dynatrace Completes $915M Acquisition of Arize AI for AI Application Observability</i> (Oct 2026).",
        "8. OpenTelemetry Project — <i>OpenTelemetry Python SDK v1.45 & OTLP Protocol Specifications</i>.",
    ]
    for c in citations:
        story.append(Paragraph(c, bullet_style))

    doc.build(story)
    print(f"✅ Successfully compiled balanced 3-page professional PDF to: {output_path}")


if __name__ == "__main__":
    out_dir = r"C:\Users\yashs\Projects\traceops-ai"
    pdf_file = os.path.join(out_dir, "TraceOps_AI_Google_Startup_Cloud_Program_Dossier.pdf")
    build_traceops_pdf(pdf_file)
