"""Tests for the OrbitronOps postmortem generator.

Pytest-style functions (same as the triage repo); also runnable via
`python -m unittest discover -s tests` is not required — CI uses pytest.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orbitronops_postmortem.models import IncidentRecord
from orbitronops_postmortem.report import (
    contains_blame_language,
    generate_postmortem,
    parse_audit_log,
    render_json,
    render_markdown,
)
from orbitronops_postmortem.rootcause import derive_root_cause
from orbitronops_postmortem.timeline import duration_seconds, format_duration, sort_timeline

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load_example() -> IncidentRecord:
    return IncidentRecord.from_dict(json.loads((EXAMPLES / "incident-oomkilled.json").read_text()))


def _minimal_record(**overrides) -> IncidentRecord:
    data = {
        "id": "INC-TEST-001",
        "service": "test-api",
        "timeline": [
            {"ts": "2026-11-15T10:00:00Z", "phase": "detection", "actor_role": "Alerting system", "description": "Alert fired."},
            {"ts": "2026-11-15T10:10:00Z", "phase": "resolution", "actor_role": "On-Call Engineer", "description": "Resolved."},
        ],
        "impact": {"services_affected": ["test-api"], "description": "Test impact."},
    }
    data.update(overrides)
    return IncidentRecord.from_dict(data)


def test_timeline_sorted_correctly():
    record = _load_example()
    sorted_events = sort_timeline(record.timeline)
    timestamps = [e.ts for e in sorted_events]
    assert timestamps == sorted(timestamps)
    assert sorted_events[0].ts == "2026-11-15T13:58:12Z"
    assert sorted_events[-1].ts == "2026-11-15T14:31:00Z"


def test_duration_computed_from_first_and_last_event():
    record = _load_example()
    assert duration_seconds(record.timeline) == 32 * 60 + 48
    assert format_duration(32 * 60 + 48) == "32m 48s"


def test_root_cause_derived_from_oomkilled_signals():
    record = _load_example()
    cause, confidence, key = derive_root_cause(record)
    assert key == "oomkilled"
    assert "OOMKilled" in cause
    assert "512Mi" in cause
    assert confidence == 0.86


def test_impact_taken_from_input_not_invented():
    record = _load_example()
    pm = generate_postmortem(record)
    assert pm.impact.failed_requests == 1240
    assert pm.impact.users_affected_approx == 860
    assert pm.impact.services_affected == ["checkout-api"]
    # No impact numbers in the input -> the postmortem says so, it does not invent.
    bare = _minimal_record()
    pm_bare = generate_postmortem(bare)
    assert pm_bare.impact.failed_requests is None
    assert pm_bare.impact.users_affected_approx is None
    text = render_markdown(pm_bare)
    assert "not recorded in the incident record" in text


def test_action_items_have_owner_role_and_priority():
    pm = generate_postmortem(_load_example())
    assert len(pm.action_items) == 6
    for item in pm.action_items:
        assert item.owner_role
        assert item.priority in {"P0", "P1", "P2"}
        assert item.due_in_days > 0
        # Owner is a role, not a person's name (no first/last name pattern).
        assert item.owner_role in {
            "Platform Engineer", "SRE / On-Call Lead", "On-Call Engineer",
        }


def test_top_action_item():
    pm = generate_postmortem(_load_example())
    top = pm.action_items[0]
    assert top.title.startswith("Validate the raised memory limit")
    assert top.priority == "P0"
    assert top.due_in_days == 7


def test_generated_postmortem_is_blameless():
    pm = generate_postmortem(_load_example())
    text = render_markdown(pm)
    assert contains_blame_language(text) is None
    assert "someone" not in text.lower()
    # No real person's name appears anywhere in the generated text.
    assert "pinkal" not in text


def test_missing_timeline_handling():
    record = _minimal_record(timeline=[])
    pm = generate_postmortem(record)
    assert pm.duration_seconds is None
    assert pm.duration_human.startswith("unknown")
    text = render_markdown(pm)
    assert "No timeline events were recorded" in text


def test_empty_timeline_single_event_has_no_duration():
    record = _minimal_record(timeline=[
        {"ts": "2026-11-15T10:00:00Z", "phase": "detection", "actor_role": "Alerting system", "description": "Alert fired."},
    ])
    pm = generate_postmortem(record)
    assert pm.duration_seconds is None


def test_json_output_valid():
    pm = generate_postmortem(_load_example())
    data = json.loads(render_json(pm))
    assert data["incident_id"] == "INC-2026-11-15-001"
    assert data["duration_seconds"] == 1968
    assert data["root_cause_confidence"] == 0.86
    assert len(data["action_items"]) == 6
    assert len(data["timeline"]) == 7


def test_audit_log_input_parsing():
    text = (EXAMPLES / "audit.jsonl").read_text()
    records = parse_audit_log(text)
    assert len(records) == 2
    assert records[0]["event"] == "triage"
    assert records[0]["probable_cause"].startswith("OOMKilled")
    assert records[1]["event"] == "approval"
    # Malformed lines are skipped, not fatal.
    assert len(parse_audit_log(text + "\nnot json\n")) == 2


def test_sample_postmortem_matches_fresh_run():
    sample = (EXAMPLES / "sample-postmortem.md").read_text()
    pm = generate_postmortem(_load_example())
    assert render_markdown(pm) == sample


def test_unknown_cause_is_honest():
    record = _minimal_record()
    cause, confidence, key = derive_root_cause(record)
    assert key == "unknown"
    assert confidence == 0.0
    assert "not determined" in cause


def test_cli_markdown_and_json():
    root = Path(__file__).resolve().parents[1]
    env = {"PYTHONPATH": str(root / "src")}
    import os

    merged = dict(os.environ)
    merged.update(env)
    md = subprocess.run(
        [sys.executable, "-m", "orbitronops_postmortem", "generate",
         str(EXAMPLES / "incident-oomkilled.json")],
        capture_output=True, text=True, cwd=root, env=merged, check=True,
    )
    assert "# Postmortem: checkout-api" in md.stdout
    assert "32m 48s" in md.stdout
    js = subprocess.run(
        [sys.executable, "-m", "orbitronops_postmortem", "generate",
         str(EXAMPLES / "incident-oomkilled.json"), "--format", "json",
         "--audit-log", str(EXAMPLES / "audit.jsonl")],
        capture_output=True, text=True, cwd=root, env=merged, check=True,
    )
    data = json.loads(js.stdout)
    assert data["incident_id"] == "INC-2026-11-15-001"
