"""
Shared Pydantic models for the Agent Skill Marketplace audit report.

Used by audit-orchestrator (final report assembly) and by the specialist
skills (crawl-render-audit, freshness-corroboration, engagement-audit) to
shape the evidence they hand back to the orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestedAction(BaseModel):
    """What the website owner should do about a finding."""

    summary: str = Field(..., min_length=1, description="Concrete, actionable fix.")
    priority: Priority


class Finding(BaseModel):
    """A single evidence-backed audit finding."""

    id: str = Field(..., description="Stable finding identifier, e.g. 'F-001'.")
    title: str = Field(..., min_length=1)
    severity: Severity
    evidence: str = Field(..., min_length=1, description="Specific, measurable evidence.")
    suggested_action: SuggestedAction

    category: Optional[str] = None
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="0-1 confidence in this finding."
    )
    affected_pages: Optional[List[str]] = None
    impact: Optional[str] = None
    implementation_notes: Optional[str] = None
    verification_method: Optional[str] = None


class Observation(BaseModel):
    """
    A raw, measured fact produced by a specialist skill BEFORE any judgment
    is applied. Observations are not automatically problems - they are the
    evidence the orchestrator/Gemini reasoning layer will later interpret
    to decide whether a real Finding exists.
    """

    id: str = Field(..., description="Stable observation identifier, e.g. 'crawl-robots-txt'.")
    skill: str = Field(..., description="Which skill produced this, e.g. 'crawl-render-audit'.")
    category: str = Field(..., description="e.g. 'crawlability', 'rendering', 'structured_data'.")
    description: str = Field(..., description="Plain-language summary of what was measured.")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Raw measured values: counts, URLs, status codes, etc."
    )


class Summary(BaseModel):
    """Counts by severity, required at the top of every report."""

    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0


class AuditReport(BaseModel):
    """The final structured output of a full audit run."""

    site: str
    audited_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of when the audit ran.",
    )
    summary: Summary = Field(default_factory=Summary)
    findings: List[Finding] = Field(default_factory=list)

    # Raw evidence collected by the specialist skills, prior to LLM reasoning
    # into Findings. Populated starting Step 10; will be consumed (and could
    # eventually be trimmed from the final report) once the Gemini reasoning
    # layer turns these into real Findings (Step 12+). Kept as a normal field
    # rather than a "debug" one since transparency into raw evidence is
    # explicitly encouraged by the brief's "additional fields" guidance.
    observations: List[Observation] = Field(default_factory=list)

    def recompute_summary(self) -> None:
        """Recalculate summary counts from the current findings list."""
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        self.summary = Summary(
            total_findings=len(self.findings),
            critical=counts[Severity.CRITICAL.value],
            high=counts[Severity.HIGH.value],
            medium=counts[Severity.MEDIUM.value],
            low=counts[Severity.LOW.value],
            informational=counts[Severity.INFORMATIONAL.value],
        )