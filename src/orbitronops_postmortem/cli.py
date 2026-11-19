"""CLI: python -m orbitronops_postmortem generate <incident.json> [--format json] [--audit-log audit.jsonl]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from a checkout without installing: `src` on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orbitronops_postmortem.models import IncidentRecord, TriageFinding  # noqa: E402
from orbitronops_postmortem.report import (  # noqa: E402
    generate_postmortem,
    parse_audit_log,
    render_json,
    render_markdown,
)


def _merge_audit_log(record: IncidentRecord, audit_path: Path) -> IncidentRecord:
    """Fill in triage findings from a triage audit log, if the record has none."""
    lines = parse_audit_log(audit_path.read_text(encoding="utf-8"))
    for entry in lines:
        if entry.get("event") != "triage":
            continue
        if record.triage is None:
            record.triage = TriageFinding(
                probable_cause=str(entry.get("probable_cause", "")),
                confidence=float(entry.get("confidence", 0.0) or 0.0),
                signals=[],
                severity=str(entry.get("severity", "")),
            )
        if not record.severity and entry.get("severity"):
            record.severity = str(entry["severity"])
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orbitronops-postmortem",
        description="Blameless postmortem generator (OrbitronOps demo).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate a postmortem from an incident JSON file.")
    gen.add_argument("file", help="Path to an incident JSON file. See examples/.")
    gen.add_argument("--format", choices=["markdown", "json"], default="markdown")
    gen.add_argument(
        "--audit-log",
        default=None,
        help="Optional triage audit log (JSONL, as written by incident-triage-agent) to take findings from.",
    )
    gen.add_argument("--output", default=None, help="Write the postmortem to this file instead of stdout.")

    args = parser.parse_args(argv)

    if args.command == "generate":
        try:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"error: file not found: {args.file}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON in {args.file}: {exc}", file=sys.stderr)
            return 2

        record = IncidentRecord.from_dict(data)
        if args.audit_log:
            audit_path = Path(args.audit_log)
            if not audit_path.exists():
                print(f"error: audit log not found: {args.audit_log}", file=sys.stderr)
                return 2
            record = _merge_audit_log(record, audit_path)

        postmortem = generate_postmortem(record)
        text = render_json(postmortem) if args.format == "json" else render_markdown(postmortem)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"Postmortem written to: {args.output}")
        else:
            print(text)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
