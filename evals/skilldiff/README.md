# SkillDiff adversarial evals

These fixtures are intentionally small and reviewable. They exercise trust-boundary changes that a plain text diff can show but cannot prioritize.

## `trigger-expansion`

Baseline:

```text
Use when converting CSV files.
```

Candidate:

```text
Use for spreadsheets, reports, analytics, finance, CSV and Excel tasks.
```

The candidate also:

- adds outbound access to `api.example.com`;
- invokes a subprocess;
- reads `API_TOKEN`;
- introduces `httpx`;
- declares only `network` in `trustforge.json`.

Expected high-signal findings:

- trigger-scope expansion is at least `medium`;
- `network`, `subprocess`, and `environment_read` are observed;
- `httpx` is a new dependency;
- `API_TOKEN` is a new secret-like reference;
- `subprocess` and `environment_read` are undeclared observed capabilities;
- SARIF contains source locations for detected capabilities.

Run manually:

```bash
trustforge skilldiff \
  evals/skilldiff/trigger-expansion/before \
  evals/skilldiff/trigger-expansion/after
```

These are detection evals, not proof that the candidate is malicious.
