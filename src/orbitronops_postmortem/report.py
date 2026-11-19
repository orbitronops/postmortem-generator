"""Generate a blameless postmortem from an incident record.

Rules:
- Impact numbers come from the input only. If the input has no number,
  the postmortem says the number is not recorded — it never invents one.
- Wording is blameless throughout: causes are attributed to systems,
  configuration, and processes, never to a person. No generated text
  names an individual.
- Deterministic: same record in, same postmortem out.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from .models import ActionItem, IncidentRecord, Postmortem
from .rootcause import derive_root_cause
from .timeline import (
    duration_seconds,
    first_event_of_phase,
    format_duration,
    phase_gap_seconds,
    sort_timeline,
)

# Words and phrases that must never appear in generated output.
# Matched as whole words/phrases, so "blameless" itself is allowed.
BLAME_PHRASES = ("blame", "fault of", "negligent", "incompetent", "careless")


def contains_blame_language(text: str) -> str | None:
    """Return the first blame phrase found in text (whole-word match), or None."""
    lowered = text.lower()
    for phrase in BLAME_PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"\b", lowered):
            return phrase
    return None

_ACTION_TEMPLATES: dict[str, list[ActionItem]] = {
    "oomkilled": [
        ActionItem(
            "Validate the raised memory limit under load and record the result",
            "Platform Engineer", "P0", 7,
        ),
        ActionItem(
            "Add a memory-usage alert at 80% of the container limit",
            "SRE / On-Call Lead", "P0", 7,
        ),
        ActionItem(
            "Add memory profiling to load tests so a growing footprint is caught before production",
            "Platform Engineer", "P1", 14,
        ),
        ActionItem(
            "Tune the CrashLoopBackOff alert so detection starts sooner",
            "SRE / On-Call Lead", "P1", 14,
        ),
        ActionItem(
            "Review memory limits for all production services against current usage",
            "Platform Engineer", "P1", 30,
        ),
        ActionItem(
            "Write down the OOMKilled runbook used during this incident",
            "On-Call Engineer", "P2", 30,
        ),
    ],
    "image_pull": [
        ActionItem("Pin image tags and verify registry credentials in CI", "Platform Engineer", "P0", 7),
        ActionItem("Add an image-pull check to the deployment pipeline", "Platform Engineer", "P1", 14),
        ActionItem("Document the image-tagging convention", "On-Call Engineer", "P2", 30),
    ],
    "node_pressure": [
        ActionItem("Add node-pressure alerts and capacity headroom checks", "SRE / On-Call Lead", "P0", 7),
        ActionItem("Review node sizing and eviction thresholds", "Platform Engineer", "P1", 14),
    ],
    "probe_failing": [
        ActionItem("Review probe timeouts against measured startup time", "Platform Engineer", "P0", 7),
        ActionItem("Add startup-time metrics to the service dashboard", "SRE / On-Call Lead", "P1", 14),
    ],
    "config_error": [
        ActionItem("Validate configuration in CI before deployment", "Platform Engineer", "P0", 7),
        ActionItem("Add a config-change checklist to the deployment runbook", "On-Call Engineer", "P1", 14),
    ],
    "triage": [
        ActionItem("Review the triage findings and confirm the follow-ups with the service owner", "SRE / On-Call Lead", "P1", 14),
    ],
    "unknown": [
        ActionItem("Complete the root-cause investigation and update this postmortem", "SRE / On-Call Lead", "P0", 7),
    ],
}


class LLMSummariser(Protocol):
    """Optional summariser. It may only reword text that already exists.

    It must never change the root cause, the confidence, any number, or
    add facts. Off by default; bring your own key. Not implemented here.
    """

    def summarise(self, text: str) -> str: ...


def _went_well(record: IncidentRecord, events) -> list[str]:
    well: list[str] = []
    detection = phase_gap_seconds(events, "detection", "acknowledgement")
    triage_gap = phase_gap_seconds(events, "acknowledgement", "triage")
    mitigation = phase_gap_seconds(events, "triage", "mitigation")
    if detection is not None and detection <= 600:
        well.append(
            f"The alert was acknowledged {format_duration(detection)} after detection."
        )
    if triage_gap is not None and triage_gap <= 600:
        well.append(
            f"The probable cause was identified {format_duration(triage_gap)} "
            "after acknowledgement, from the triage findings."
        )
    if mitigation is not None and mitigation <= 900:
        well.append(
            f"Mitigation started {format_duration(mitigation)} after the cause "
            "was identified."
        )
    if first_event_of_phase(events, "resolution") is not None:
        well.append("The incident was declared resolved only after the service was healthy again.")
    if record.triage and record.triage.confidence >= 0.8:
        well.append(
            "Triage produced a high-confidence cause from the recorded signals, "
            "so the response worked from evidence rather than guesswork."
        )
    if not well:
        well.append("The timeline and triage findings were recorded, so the incident can be reviewed.")
    return well


def _went_wrong(record: IncidentRecord, events) -> list[str]:
    wrong: list[str] = []
    first = sort_timeline(events)[0] if events else None
    detection_event = first_event_of_phase(events, "detection")
    if first is not None and detection_event is not None and first is not detection_event:
        from .timeline import parse_ts

        gap = phase_gap_seconds(events, "other", "detection")
        start, detected = parse_ts(first.ts), parse_ts(detection_event.ts)
        if start is not None and detected is not None:
            delay = int((detected - start).total_seconds())
            if delay > 180:
                wrong.append(
                    f"Detection took {format_duration(delay)} after the first "
                    "observed failure — there was no alert on the early signal."
                )
    if record.triage and record.triage.probable_cause.lower().startswith("oomkilled"):
        wrong.append(
            "There was no memory-usage alert before the container hit its limit, "
            "so the first signal was the crash itself."
        )
    if not wrong:
        wrong.append("No systemic gap is visible in the recorded timeline.")
    return wrong


def generate_postmortem(record: IncidentRecord) -> Postmortem:
    events = sort_timeline(record.timeline)
    duration = duration_seconds(events)
    cause, confidence, cause_key = derive_root_cause(record)
    factors = list(record.contributing_factors)
    if cause_key == "oomkilled" and not any(
        "memory limit" in f.lower() for f in factors
    ):
        factors.append("The memory limit had not been reviewed against current usage.")
    return Postmortem(
        incident_id=record.id,
        service=record.service,
        severity=record.severity or (record.triage.severity if record.triage else ""),
        duration_seconds=duration,
        duration_human=format_duration(duration),
        root_cause=cause,
        root_cause_confidence=confidence,
        impact=record.impact,
        timeline=events,
        contributing_factors=factors,
        went_well=_went_well(record, events),
        went_wrong=_went_wrong(record, events),
        action_items=list(_ACTION_TEMPLATES.get(cause_key, _ACTION_TEMPLATES["unknown"])),
    )


def render_markdown(pm: Postmortem) -> str:
    lines = [
        f"# Postmortem: {pm.service} — {pm.incident_id}",
        "",
        "> Blameless postmortem. This document describes what the system did, "
        "what the process did, and what to change — it does not attribute the "
        "incident to any person.",
        "",
        "## Summary",
        "",
        f"- **Service:** {pm.service}",
        f"- **Severity:** {pm.severity or 'not recorded'}",
        f"- **Duration:** {pm.duration_human}",
        f"- **Root cause:** {pm.root_cause}",
        f"- **Root-cause confidence:** {pm.root_cause_confidence:.2f}",
        "",
        "## Impact",
        "",
    ]
    if pm.impact.description:
        lines.append(pm.impact.description)
        lines.append("")
    if pm.impact.services_affected:
        lines.append(f"- **Services affected:** {', '.join(pm.impact.services_affected)}")
    if pm.impact.users_affected_approx is not None:
        lines.append(f"- **Users affected (approx.):** {pm.impact.users_affected_approx}")
    else:
        lines.append("- **Users affected:** not recorded in the incident record")
    if pm.impact.failed_requests is not None:
        lines.append(f"- **Failed requests:** {pm.impact.failed_requests}")
    else:
        lines.append("- **Failed requests:** not recorded in the incident record")
    lines += ["", "## Timeline", ""]
    if pm.timeline:
        lines.append("| Time (UTC) | Phase | Actor (role) | What happened |")
        lines.append("|---|---|---|---|")
        for event in pm.timeline:
            lines.append(
                f"| {event.ts} | {event.phase} | {event.actor_role or '—'} | {event.description} |"
            )
    else:
        lines.append("No timeline events were recorded for this incident.")
    lines += ["", "## Root cause", "", pm.root_cause, ""]
    lines += ["## Contributing factors", ""]
    for factor in pm.contributing_factors:
        lines.append(f"- {factor}")
    if not pm.contributing_factors:
        lines.append("None recorded.")
    lines += ["", "## What went well", ""]
    for item in pm.went_well:
        lines.append(f"- {item}")
    lines += ["", "## What went wrong", ""]
    for item in pm.went_wrong:
        lines.append(f"- {item}")
    lines += ["", "## Action items", ""]
    lines.append("| # | Action | Owner (role) | Priority | Due in |")
    lines.append("|---|---|---|---|---|")
    for i, action in enumerate(pm.action_items, 1):
        lines.append(
            f"| {i} | {action.title} | {action.owner_role} | {action.priority} | {action.due_in_days} days |"
        )
    lines += [
        "",
        "## Prevention / follow-ups",
        "",
        "Each action item above is tracked by role and priority, not by person. "
        "Re-run this generator after the actions are done and compare the new "
        "timeline against this one — the next postmortem is the check that the "
        "fixes worked.",
        "",
        "---",
        "",
        "*Generated by the OrbitronOps postmortem generator (demo). "
        "No client work is claimed for this document.*",
        "",
    ]
    text = chr(10).join(lines)
    leaked = contains_blame_language(text)
    assert leaked is None, f"blame phrase leaked into output: {leaked}"
    return text


def render_json(pm: Postmortem) -> str:
    return json.dumps(pm.to_dict(), indent=2)


def parse_audit_log(text: str) -> list[dict]:
    """Parse triage-style JSONL audit lines (as written by incident-triage-agent)."""
    records: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
