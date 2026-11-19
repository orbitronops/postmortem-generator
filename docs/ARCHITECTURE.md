# Architecture

## Design goals

1. **A stranger can run it in 2 minutes** — no API key, no cluster, no cloud bill.
2. **Deterministic** — same incident in, same postmortem out. No hidden randomness in the demo path.
3. **Blameless by construction** — the generator attributes causes to systems, configuration, and processes, never to a person. Action-item owners are roles, never names.

## Flow

```
Incident JSON (timeline + triage findings + impact)
  → models.IncidentRecord.from_dict()
  → timeline.sort_timeline() / duration_seconds()
  → rootcause.derive_root_cause()   # deterministic rules, mirrors incident-triage-agent
  → report.generate_postmortem()    # went well / went wrong from timeline gaps
  → report.render_markdown() / render_json()
```

An optional `--audit-log` takes triage findings from an
`incident-triage-agent` audit log (`audit/audit.jsonl`) instead of the
incident file, so the postmortem agrees with the triage it was built from.

## Extension points

| Want to add… | Where |
|---|---|
| A new failure pattern | A new branch in `rootcause.derive_root_cause()` + a test in `tests/test_postmortem.py` |
| A new action-item template | A new entry in `report._ACTION_TEMPLATES` |
| Slack / PagerDuty ingestion | A new `connectors/alerts.py` that converts an alert payload to an `IncidentRecord` |
| LLM summariser | Implement `report.LLMSummariser.summarise()` — it may only reword text that already exists. It must never change the root cause, confidence, or any number. Off by default, bring your own key. |

## What this is not (yet)

- Not a live incident system — the demo uses sample JSON, not a real alerting or ticketing API.
- Not a substitute for the review meeting — the document is a draft for humans to discuss, correct, and approve.
- Not a client delivery — see README Status. It is a prototype that shows how OrbitronOps builds.
