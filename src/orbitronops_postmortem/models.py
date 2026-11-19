"""Data models for the postmortem generator. Plain dataclasses, no dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TimelineEvent:
    """One timestamped event in the incident timeline."""

    ts: str  # ISO 8601, e.g. 2026-11-15T14:02:00Z
    phase: str = "other"  # detection | acknowledgement | triage | mitigation | resolution | other
    actor_role: str = ""  # a role, never a person's name
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "TimelineEvent":
        return cls(
            ts=str(data.get("ts", "")),
            phase=str(data.get("phase", "other")),
            actor_role=str(data.get("actor_role", "")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict:
        return {"ts": self.ts, "phase": self.phase,
                "actor_role": self.actor_role, "description": self.description}


@dataclass
class TriageFinding:
    """A triage finding, in the shape the incident-triage-agent produces."""

    probable_cause: str = ""
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    severity: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "TriageFinding":
        return cls(
            probable_cause=str(data.get("probable_cause", "")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            signals=[str(s) for s in data.get("signals", [])],
            severity=str(data.get("severity", "")),
        )

    def to_dict(self) -> dict:
        return {"probable_cause": self.probable_cause, "confidence": self.confidence,
                "signals": self.signals, "severity": self.severity}


@dataclass
class Impact:
    """Impact, taken from the incident record — never invented by the generator."""

    services_affected: list[str] = field(default_factory=list)
    users_affected_approx: int | None = None
    failed_requests: int | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Impact":
        return cls(
            services_affected=[str(s) for s in data.get("services_affected", [])],
            users_affected_approx=data.get("users_affected_approx"),
            failed_requests=data.get("failed_requests"),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict:
        return {"services_affected": self.services_affected,
                "users_affected_approx": self.users_affected_approx,
                "failed_requests": self.failed_requests,
                "description": self.description}


@dataclass
class IncidentRecord:
    """A full incident record: timeline + triage findings + impact."""

    id: str
    service: str
    namespace: str = "prod"
    severity: str = ""
    status: str = "resolved"
    timeline: list[TimelineEvent] = field(default_factory=list)
    triage: TriageFinding | None = None
    impact: Impact = field(default_factory=Impact)
    contributing_factors: list[str] = field(default_factory=list)
    # Raw triage signals, e.g. exit code / memory usage, for root-cause rules.
    last_exit_code: int | None = None
    last_terminated_reason: str = ""
    memory_usage_mi: int | None = None
    memory_limit_mi: int | None = None
    log_snippet: str = ""
    node_condition: str = ""
    probe_failing: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "IncidentRecord":
        return cls(
            id=str(data.get("id", "unknown")),
            service=str(data.get("service", "unknown")),
            namespace=str(data.get("namespace", "prod")),
            severity=str(data.get("severity", "")),
            status=str(data.get("status", "resolved")),
            timeline=[TimelineEvent.from_dict(e) for e in data.get("timeline", [])],
            triage=TriageFinding.from_dict(data["triage"]) if data.get("triage") else None,
            impact=Impact.from_dict(data.get("impact", {})),
            contributing_factors=[str(f) for f in data.get("contributing_factors", [])],
            last_exit_code=data.get("last_exit_code"),
            last_terminated_reason=str(data.get("last_terminated_reason", "")),
            memory_usage_mi=data.get("memory_usage_mi"),
            memory_limit_mi=data.get("memory_limit_mi"),
            log_snippet=str(data.get("log_snippet", "")),
            node_condition=str(data.get("node_condition", "")),
            probe_failing=str(data.get("probe_failing", "")),
        )


@dataclass
class ActionItem:
    """One follow-up. Owner is a role, never a person's name."""

    title: str
    owner_role: str
    priority: str  # P0 | P1 | P2
    due_in_days: int

    def to_dict(self) -> dict:
        return {"title": self.title, "owner_role": self.owner_role,
                "priority": self.priority, "due_in_days": self.due_in_days}


@dataclass
class Postmortem:
    """A generated, blameless postmortem."""

    incident_id: str
    service: str
    severity: str
    duration_seconds: int | None
    duration_human: str
    root_cause: str
    root_cause_confidence: float
    impact: Impact
    timeline: list[TimelineEvent] = field(default_factory=list)
    contributing_factors: list[str] = field(default_factory=list)
    went_well: list[str] = field(default_factory=list)
    went_wrong: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "severity": self.severity,
            "duration_seconds": self.duration_seconds,
            "duration_human": self.duration_human,
            "root_cause": self.root_cause,
            "root_cause_confidence": self.root_cause_confidence,
            "impact": self.impact.to_dict(),
            "timeline": [e.to_dict() for e in self.timeline],
            "contributing_factors": self.contributing_factors,
            "went_well": self.went_well,
            "went_wrong": self.went_wrong,
            "action_items": [a.to_dict() for a in self.action_items],
        }
