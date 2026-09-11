---
name: skilldiff
description: Audit two versions of an AI agent skill and surface capability, trigger-scope, dependency, secret-access, file, AST, and network-domain changes before the updated skill is trusted or installed.
license: Apache-2.0
metadata:
  trustforge:
    maturity: experimental
    category: supply-chain
    destructive: false
---

# SkillDiff

Use SkillDiff when an agent skill, prompt package, MCP helper, or repository automation has changed and you need to know whether the candidate version crossed a new trust boundary.

## Goal

Produce a human-readable or machine-readable change report that answers:

1. Which files were added, removed, or changed?
2. Which risky capabilities appear in the candidate but not the baseline?
3. Where exactly was each capability detected?
4. Does structured Python syntax reveal behavior that lexical matching missed?
5. Did the skill's trigger/selection scope become broader?
6. Which outbound domains and dependencies are new?
7. Did the candidate start referencing secret-like environment variables?
8. Does observed behavior match the declared capability manifest?
9. What is the resulting review risk?

SkillDiff is intentionally **not** a malware detector. A clean report is not proof that a skill is safe.

## Inputs

- `before`: directory containing the previously trusted skill version.
- `after`: directory containing the candidate skill version.

Neither directory is executed by the static scanners.

## Output

The v0.3 report includes:

- file delta;
- lexical capability delta;
- Python AST capability delta;
- evidence locations with path, line number, symbol, detector, and confidence where available;
- added/removed network domains;
- dependency delta;
- secret-like environment reference delta;
- trigger-scope lexical expansion estimate;
- capability-manifest declared-vs-observed comparison;
- heuristic risk score plus human-readable explanations;
- JSON or SARIF 2.1.0 export.

Current capability classes:

- `network`
- `subprocess`
- `environment_read`
- `filesystem_read`
- `filesystem_write`
- `dynamic_execution`
- `credential_material`

## Python AST detector

SkillDiff v0.3 parses Python source with the standard-library `ast` module and never imports or executes candidate Python files.

The first structured detector resolves common aliases, including patterns such as:

```python
import subprocess as sp
import requests as rq
from os import getenv as read_env

read_env("DEPLOY_TOKEN")
rq.post(endpoint, json=payload)
sp.run(["echo", "done"], check=True)
```

It also distinguishes `open()` modes:

```python
open("input.txt", "r")   # filesystem_read
open("output.txt", "w") # filesystem_write
open("state.db", "r+")  # read + write
```

AST evidence includes the normalized symbol, detector name, source line, and a confidence level. Regex/lexical scanning remains active because it covers non-Python files and indicators that do not require structured parsing.

## Capability manifest

A candidate skill may include `trustforge.json`:

```json
{
  "capabilities": [
    "network",
    "filesystem_read"
  ]
}
```

SkillDiff reports:

- `undeclared_observed`: statically observed capabilities absent from the manifest;
- `declared_not_observed`: declared capabilities not observed by the current static detectors.

The manifest is a review contract, not a sandbox permission system.

A minimal YAML list in `trustforge.yaml` or `trustforge.yml` is also supported.

## Trigger-scope diff

SkillDiff extracts trigger language from `SKILL.md`, prioritizing frontmatter `description` and explicit “use/trigger/invoke ... when/for” lines.

Example:

```text
Before:
Use when converting CSV files.

After:
Use for spreadsheets, reports, analytics, finance, CSV and Excel tasks.
```

The report identifies newly introduced terms and estimates expansion as `none`, `low`, `medium`, `high`, or `unknown`.

This is deliberately lexical and heuristic. It should flag review-worthy scope expansion, not claim semantic proof.

## CLI

Human-readable output:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2
```

JSON:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2 --format json
```

`--json` remains available as a compatibility alias.

SARIF 2.1.0:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2 --format sarif > skilldiff.sarif
```

Fail CI when the candidate introduces medium-or-higher risk:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2 --fail-on medium
```

Exit codes:

- `0`: report generated and configured threshold not reached.
- `2`: configured risk threshold reached.

## GitHub Action

The repository root contains a composite action. Example:

```yaml
- uses: actions/checkout@v4
- uses: ptrgiang/trustforge-skills@main
  with:
    before: fixtures/trusted-skill
    after: skills/candidate-skill
    fail-on: medium
    format: sarif
    report-path: artifacts/skilldiff.sarif
```

For production workflows, pin a release tag or immutable commit SHA when one is available.

## Evidence rules

When reporting a capability change:

- identify the capability by name;
- include path and line number where possible;
- identify which detector produced the evidence;
- distinguish a newly added capability from one that already existed;
- do not infer malicious intent from a pattern alone.

Good:

> `subprocess` is newly detected by `python-ast-v1` at `scripts/install.py:42` through `subprocess.run`.

Bad:

> This update is malicious.

## Risk scoring

The score increases for newly introduced:

- capabilities, weighted by impact;
- network domains;
- dependencies;
- secret-like environment references;
- medium/high trigger-scope expansion;
- observed capabilities omitted from a present capability manifest;
- capabilities discovered by the AST layer that the lexical layer missed.

The score is a triage signal, not a security verdict.

## Failure modes

Static SkillDiff may miss capabilities implemented through:

- obfuscation;
- generated code;
- binaries;
- runtime downloads;
- reflection and highly dynamic dispatch;
- unsupported language APIs;
- transitive dependency behavior;
- prompt-induced tool use that has no static indicator.

Python files with syntax unsupported by the running interpreter are reported as AST parse errors rather than silently treated as fully scanned.

False positives remain possible because the overall detector is intentionally conservative.

## Next work

- JavaScript/TypeScript AST detection;
- transitive dependency capability analysis;
- signed baseline manifests;
- behavioral canary replay in an isolated sandbox;
- richer trigger-scope models and benchmark datasets.
