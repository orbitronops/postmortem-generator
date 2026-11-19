# OrbitronOps Postmortem Generator

> **A blameless postmortem generator.** It reads an incident timeline and
> triage findings and writes a structured postmortem — summary, impact,
> timeline, root cause, what went well / what went wrong, and action items
> owned by role, never by person.

[![CI](https://github.com/orbitronops/postmortem-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/orbitronops/postmortem-generator/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Demo](https://img.shields.io/badge/status-demo%20%E2%80%94%20not%20client%20work-lightgrey.svg)](#status)

**By [OrbitronOps](https://www.orbitronops.com)** — Production AI Infrastructure on Kubernetes.
North Vancouver, BC · Canada Remote / BC Hybrid

---

## What this proves

A buyer doesn't have to take our word for it. They can run this in 2 minutes:

```bash
git clone https://github.com/orbitronops/postmortem-generator.git
cd postmortem-generator
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json
```

And get a postmortem like this:

```
# Postmortem: checkout-api — INC-2026-11-15-001

- **Service:** checkout-api
- **Severity:** HIGH
- **Duration:** 32m 48s
- **Root cause:** OOMKilled — the checkout-api container exceeded its memory
  limit (511Mi used of 512Mi). The container was terminated with exit code
  137 and restarted, which repeated until the limit was raised.
- **Root-cause confidence:** 0.86

## Impact

- **Services affected:** checkout-api
- **Users affected (approx.):** 860
- **Failed requests:** 1240

## Action items

| # | Action | Owner (role) | Priority | Due in |
|---|---|---|---|---|
| 1 | Validate the raised memory limit under load and record the result | Platform Engineer | P0 | 7 days |
| 2 | Add a memory-usage alert at 80% of the container limit | SRE / On-Call Lead | P0 | 7 days |
| 3 | Add memory profiling to load tests so a growing footprint is caught before production | Platform Engineer | P1 | 14 days |
```

The full output is in [`examples/sample-postmortem.md`](examples/sample-postmortem.md).

No API key needed for the demo. No cluster needed. No cloud bill.

## How it pairs with the incident-triage-agent

The triage agent answers "what is happening, right now?" This generator
answers "what happened, why, and what do we change?" — the next step in the
same incident.

It reads the triage agent's audit log directly:

```bash
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json \
  --audit-log examples/audit.jsonl --format json
```

The `--audit-log` option takes triage findings from an
[`incident-triage-agent`](https://github.com/orbitronops/incident-triage-agent)
audit log (`audit/audit.jsonl`), so the postmortem's root cause agrees with
the triage it was built from. The root-cause rules mirror the triage agent's
rules for the same reason.

## Why blameless?

A postmortem that names a person teaches the team to hide the next incident.
This generator attributes causes to systems, configuration, and processes:

1. **No names** — action-item owners are roles (`Platform Engineer`,
   `SRE / On-Call Lead`), never a person's name.
2. **No blame language** — the wording is checked by a test
   (`test_generated_postmortem_is_blameless`).
3. **No invented facts** — impact numbers come from the incident record.
   If a number is not in the input, the postmortem says it is not recorded.

## Quickstart

**Requirements:** Python 3.10+ only. No dependencies for the demo.

```bash
# 1. Clone
git clone https://github.com/orbitronops/postmortem-generator.git
cd postmortem-generator

# 2. Generate the sample postmortem (Markdown)
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json

# 3. Or JSON, for tooling
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json --format json

# 4. Or take the triage findings from a triage audit log
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json \
  --audit-log examples/audit.jsonl

# 5. Run the tests
python -m pytest -q
# or, with no pytest installed:
python -m unittest discover -s tests -v
```

### Try your own incident

Copy an example and edit it:

```bash
cp examples/incident-oomkilled.json my-incident.json
# edit my-incident.json, then:
PYTHONPATH=src python3 -m orbitronops_postmortem generate my-incident.json
```

See [`examples/`](examples/) for the incident schema, and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the generator works.

## How it works

```
Incident JSON (timeline + triage + impact)
  → Timeline: sorted, duration, phase gaps
  → Root cause: deterministic rules from triage signals
  → Went well / went wrong: derived from timeline gaps
  → Action items: templates per cause, owned by role
  → Postmortem (Markdown / JSON)
```

| Incident signal | Root cause | Confidence |
|---|---|---|
| `OOMKilled` + exit 137 + memory at limit | OOMKilled — memory limit too low | High |
| `ImagePullBackOff` / `ErrImagePull` | Image tag missing, or registry auth | High |
| Pod evicted / `NodePressure` | Node disk / memory pressure | Medium |
| Readiness probe failing | App not ready, or probe too strict | Medium |
| Config error in logs | Bad config / missing env var | Medium |
| No signal points to a cause | Root cause not determined — says so plainly | 0.00 |

The engine is deliberately deterministic for the demo — same input, same
output, every time. An LLM summariser is a pluggable interface
(`report.LLMSummariser` — optional, bring your own key), never required,
and it may only reword text that already exists: it must never change the
root cause, the confidence, or any number.

## Project layout

```
.
├── src/orbitronops_postmortem/  # the generator: models, timeline, root cause, report, CLI
│   ├── models.py                # IncidentRecord / TimelineEvent / Postmortem / ActionItem
│   ├── timeline.py              # sorting, duration, phase gaps
│   ├── rootcause.py             # deterministic root-cause rules
│   ├── report.py                # postmortem generation + Markdown / JSON rendering
│   └── cli.py                   # `python -m orbitronops_postmortem generate <file>`
├── examples/                    # sample incident + triage audit log + sample postmortem
│   ├── incident-oomkilled.json  # fictional checkout-api OOMKilled incident
│   ├── audit.jsonl              # matching triage-style audit log
│   └── sample-postmortem.md     # actual output for incident-oomkilled.json
├── tests/                       # 14 tests for timeline, root cause, blame, output
├── docs/
│   ├── ARCHITECTURE.md          # design, flow, extension points
│   └── SECURITY.md              # what the generator can / cannot do
├── .github/workflows/ci.yml     # lint + tests on every push
├── Dockerfile                   # run the demo in a container, no local Python needed
└── pyproject.toml
```

## Status

**Demo — not client work.**

OrbitronOps has not yet delivered a client postmortem using this generator.
This repository is a working prototype built to show how we build one: the
structure, the blameless wording, and the action items a client would
actually get. No client names, no client results, and no client data appear
anywhere in it.

If you want this wired to *your* incidents, alerts, and runbooks, talk to
us: [orbitronops.com](https://www.orbitronops.com) ·
[LinkedIn](https://www.linkedin.com/company/orbitronops/)

## Roadmap

- [x] Deterministic postmortem from timeline + triage findings + impact
- [x] Triage audit-log input (pairs with incident-triage-agent)
- [ ] Slack / PagerDuty alert ingestion
- [ ] Postmortem review workflow (draft → human approval → published)
- [ ] Action-item tracking: re-run after the actions are done and compare
- [ ] Optional LLM summariser (pluggable, off by default)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome — please keep
the blameless rule intact.

## License

MIT — see [LICENSE](LICENSE).
```

