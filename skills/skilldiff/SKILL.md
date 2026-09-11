---
name: skilldiff
description: Audit two versions of an AI agent skill and surface capability, trigger-scope, dependency, secret-access, file, and network-domain changes before the updated skill is trusted or installed.
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
4. Did the skill's trigger/selection scope become broader?
5. Which outbound domains and dependencies are new?
6. Did the candidate start referencing secret-like environment variables?
7. Does observed behavior match the declared capability manifest?
8. What is the resulting review risk?

SkillDiff is intentionally **not** a malware detector. A clean report is not proof that a skill is safe.

## Inputs

- `before`: directory containing the previously trusted skill version.
- `after`: directory containing the candidate skill version.

Neither directory is executed by the static scanner.

## Output

The v0.2 report includes:

- file delta;
- added/removed capability classes;
- evidence locations with path, line number, and excerpt;
- added/removed network domains;
- dependency delta;
- secret-like environment reference delta;
- trigger-scope lexical expansion estimate;
- capability-manifest declared-vs-observed comparison;
- heuristic risk score plus human-readable explanations.

Current capability classes:

- `network`
- `subprocess`
- `environment_read`
- `filesystem_read`
- `filesystem_write`
- `dynamic_execution`
- `credential_material`

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
- `declared_not_observed`: declared capabilities not observed by the current static detector.

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

## Evidence rules

When reporting a capability change:

- identify the capability by name;
- include path and line number where possible;
- distinguish a newly added capability from one that already existed;
- do not infer malicious intent from a pattern alone.

Good:

> `subprocess` is newly detected at `scripts/install.py:42`.

Bad:

> This update is malicious.

## Risk scoring

The v0.2 score increases for newly introduced:

- capabilities, weighted by impact;
- network domains;
- dependencies;
- secret-like environment references;
- medium/high trigger-scope expansion;
- observed capabilities omitted from a present capability manifest.

The score is a triage signal, not a security verdict.

## Failure modes

Static SkillDiff may miss capabilities implemented through:

- obfuscation;
- generated code;
- binaries;
- runtime downloads;
- unusual language APIs;
- transitive dependency behavior;
- prompt-induced tool use that has no static indicator.

False positives are possible because the detector is intentionally conservative.

## Next work

- language-aware AST detectors;
- transitive dependency capability analysis;
- behavioral canary replay in an isolated sandbox;
- signed baseline manifests;
- richer trigger-scope models and benchmark datasets.
