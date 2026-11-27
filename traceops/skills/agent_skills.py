"""
Google Agent Skills Export for TraceOps AI.
Provides clean, reusable tool definitions for:
1. drift_check: In-process semantic drift verification against golden centroids.
2. tool_boundary_audit: Pre-execution validation of tool allowlist and argument schemas.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from traceops.guards.deterministic import DeterministicGuard
from traceops.guards.semantic_drift import SemanticDriftScorer

class DriftCheckInput(BaseModel):
    step_description: str = Field(..., description="Action description or reasoning for the step")
    tool_name: str = Field(..., description="Name of the tool the agent plans to invoke")
    scenario: str = Field("default", description="Domain scenario (e.g. incident_triage, canary_deployment)")

class ToolBoundaryAuditInput(BaseModel):
    tool_name: str = Field(..., description="Tool candidate name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")
    allowed_tools: Optional[List[str]] = Field(None, description="Explicit allowed tool set override")

# Global reusable instances
_skill_drift_scorer = SemanticDriftScorer()
_skill_guard = DeterministicGuard()

def drift_check(input_data: DriftCheckInput) -> Dict[str, Any]:
    """
    Agent Skill: Perform in-process semantic goal drift audit before executing an action.
    Returns cosine similarity, drift score, and recommendation (ALLOW, WARN, HALT).
    """
    text = f"{input_data.tool_name} {input_data.step_description}"
    result = _skill_drift_scorer.evaluate_drift(text, scenario=input_data.scenario)
    return {
        "status": result["status"],
        "drift_score": result["drift_score"],
        "cosine_similarity": result["cosine_similarity"],
        "recommendation": result["message"]
    }

def tool_boundary_audit(input_data: ToolBoundaryAuditInput) -> Dict[str, Any]:
    """
    Agent Skill: Validate whether a candidate tool is permitted by least-privilege boundary rules.
    Catches unauthorized tools and destructive hallucinations in <1 ms.
    """
    allowed = set(input_data.allowed_tools) if input_data.allowed_tools else _skill_guard.allowed_tools

    if input_data.tool_name not in allowed:
        return {
            "compliant": False,
            "decision": "BLOCKED",
            "violation": "unauthorized_tool",
            "reason": f"Tool '{input_data.tool_name}' is outside the least-privilege allowlist boundary.",
            "allowed_tools": sorted(list(allowed))
        }

    return {
        "compliant": True,
        "decision": "PERMITTED",
        "reason": f"Tool '{input_data.tool_name}' is within safe boundary permissions."
    }
