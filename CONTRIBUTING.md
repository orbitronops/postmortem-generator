# Contributing

Thanks for looking at this OrbitronOps demo.

## Ground rules

1. **Blameless stays blameless.** No PR may add wording that names or blames an
   individual, or that attributes the incident to a person rather than to a
   system, a process, or a gap in tooling. The test
   `test_generated_postmortem_is_blameless` enforces this.
2. **No invented facts.** Impact numbers, durations, and causes must come from
   the incident record or be derived deterministically from it. Do not add a
   number the input does not support.
3. **No fake client claims.** Do not add a case study, logo, or testimonial for
   work that did not happen. This is a demo prototype.
4. **Every new rule needs a test.** Add the incident to `examples/` if it is a
   good demo, and a test in `tests/test_postmortem.py`.

## Running it locally

```bash
PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json
python -m pytest -q
```
