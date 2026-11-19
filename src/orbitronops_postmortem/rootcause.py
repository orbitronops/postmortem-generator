"""Deterministic root-cause derivation from triage findings and raw signals.

Same input -> same cause, every time. The rules mirror the
incident-triage-agent's rules so a postmortem built from its audit log
agrees with the triage it was built from. Nothing here calls an LLM:
the optional summariser interface (see report.py) may only reword text
that already exists, never change the cause or its confidence.
"""
from __future__ import annotations

from .models import IncidentRecord


def _memory_at_limit(record: IncidentRecord) -> bool:
    if record.memory_usage_mi is None or record.memory_limit_mi is None:
        return False
    if record.memory_limit_mi <= 0:
        return False
    return record.memory_usage_mi / record.memory_limit_mi >= 0.95


def derive_root_cause(record: IncidentRecord) -> tuple[str, float, str]:
    """Return (root_cause, confidence, cause_key)."""
    triage = record.triage
    cause_text = (triage.probable_cause if triage else "").lower()
    signals = [s.lower() for s in (triage.signals if triage else [])]

    if (
        record.last_terminated_reason.lower() == "oomkilled"
        or record.last_exit_code == 137
        or "oomkilled" in cause_text
    ):
        if record.memory_limit_mi is not None and record.memory_usage_mi is not None:
            cause = (
                f"OOMKilled — the {record.service} container exceeded its memory "
                f"limit ({record.memory_usage_mi}Mi used of {record.memory_limit_mi}Mi). "
                "The container was terminated with exit code 137 and restarted, "
                "which repeated until the limit was raised."
            )
        else:
            cause = (
                f"OOMKilled — the {record.service} container exceeded its memory "
                "limit and was terminated with exit code 137."
            )
        return cause, 0.86, "oomkilled"

    if "image pull" in cause_text or any("imagepull" in s for s in signals):
        return (
            "Image pull failure — the container image tag was missing, or the "
            "registry credentials were not accepted, so the pod could not start.",
            0.82,
            "image_pull",
        )

    if record.node_condition:
        return (
            f"Node pressure — {record.node_condition} on the node hosting "
            f"{record.service} degraded the workload.",
            0.71,
            "node_pressure",
        )

    if record.probe_failing:
        return (
            "Readiness / liveness probe failing — the application was slow to "
            "start, or the probe was stricter than the application's startup time.",
            0.68,
            "probe_failing",
        )

    if "config" in cause_text or "config" in record.log_snippet.lower():
        return (
            "Configuration error — the application started with a bad or missing "
            "configuration value and exited.",
            0.65,
            "config_error",
        )

    if triage and triage.probable_cause:
        return triage.probable_cause, triage.confidence, "triage"

    return (
        "Root cause not determined from the available signals — the timeline and "
        "triage findings do not point to a single cause. Further investigation "
        "is needed before a cause is stated.",
        0.0,
        "unknown",
    )
