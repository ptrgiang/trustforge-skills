# TrustForge Skills

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

The project starts from a simple observation: as agent ecosystems grow, the hard problem is no longer only *what can an agent do?* It is also:

- Did a skill silently gain new capabilities?
- Did its trigger scope quietly become much broader?
- Did the agent satisfy every user constraint before claiming completion?
- Did it expose more data than the task required?
- Is the plan still valid after external facts changed?
- Can a failure be reproduced by another developer?

TrustForge turns those questions into reusable skills, contracts, evidence, evals, and CI gates.

## Current focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.3 flagship** |
| **CommitmentGuard** | Require evidence for user constraints before an agent can claim completion | MVP |
| **DataLease** | Minimize and gate data shared with tools/APIs | Planned |
| **FreshPlan** | Invalidate plan nodes when facts become stale | Planned |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## Why SkillDiff

A normal file diff answers **what text changed**. SkillDiff tries to answer **what trust assumptions changed**.

The v0.3 pipeline combines lexical scanning with Python AST analysis:

```text
files
  ↓
lexical capability scan + evidence locations
  ↓
Python AST capability scan
  ↓
network domains + dependencies
  ↓
secret-like environment access
  ↓
SKILL.md trigger-scope expansion
  ↓
declared vs observed capability manifest
  ↓
risk explanations + JSON/SARIF + CI gate
```

The AST layer resolves aliases and call structure instead of merely matching suspicious text. For example, it can distinguish a string containing `subprocess.run(...)` from an actual aliased call such as `import subprocess as sp; sp.run(...)`.

Current Python AST detectors cover:

- network clients such as `requests`, `httpx`, `urllib.request`, `socket`, and `aiohttp`;
- subprocess execution, including imported aliases;
- environment-variable reads and secret-like env names;
- `open()` read/write mode;
- common filesystem read/write and mutation calls;
- dynamic execution via `eval`, `exec`, and `compile`.

SkillDiff remains a static review tool, **not** a malware detector. A clean report is not proof that a candidate is safe.

## Quick start

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

Run SkillDiff:

```bash
trustforge skilldiff ./before-skill ./after-skill
```

Machine-readable output:

```bash
trustforge skilldiff ./before-skill ./after-skill --format json
trustforge skilldiff ./before-skill ./after-skill --format sarif > skilldiff.sarif
```

Use it as a CI gate:

```bash
trustforge skilldiff ./before-skill ./after-skill --fail-on medium
```

## GitHub Action

TrustForge now ships a composite GitHub Action from the repository root.

Until a stable tag is published, pin the action to a commit SHA or use `@main` for evaluation:

```yaml
name: Skill trust check

on:
  pull_request:

jobs:
  skilldiff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ptrgiang/trustforge-skills@main
        with:
          before: fixtures/trusted-skill
          after: skills/candidate-skill
          fail-on: medium
          format: sarif
          report-path: artifacts/skilldiff.sarif
```

Action inputs:

- `before` — trusted/baseline skill directory;
- `after` — candidate skill directory;
- `fail-on` — optional `low`, `medium`, or `high` threshold;
- `format` — `text`, `json`, or `sarif`;
- `report-path` — optional file to receive the report;
- `python-version` — defaults to Python 3.12.

For production use, prefer a release tag or immutable commit SHA rather than a moving branch.

## Adversarial evals

Two small eval families live under `evals/skilldiff/`:

- `trigger-expansion` exercises trigger broadening, new domains, dependencies, secret references, and manifest mismatch;
- `python-ast-alias` deliberately places a dangerous-looking call inside a harmless string in the baseline, then introduces real aliased network/subprocess/env/file-write calls in the candidate.

Run the AST eval:

```bash
trustforge skilldiff \
  evals/skilldiff/python-ast-alias/before \
  evals/skilldiff/python-ast-alias/after
```

## Capability manifests

A skill can declare expected capabilities in `trustforge.json`:

```json
{
  "capabilities": ["network", "filesystem_read"]
}
```

SkillDiff compares the declaration with capabilities observed by the static scanners and surfaces mismatches for review.

## CommitmentGuard

```bash
trustforge verify examples/refactor-contract.json \
  --evidence examples/refactor-evidence.json
```

CommitmentGuard blocks a verified-complete result while required evidence remains `FAIL` or `UNKNOWN`, unless a commitment has an explicit waiver.

## Core idea

```text
SkillDiff → DataLease → FreshPlan → CommitmentGuard → ReproCapsule

Can I trust this skill?
        ↓
What data may it use?
        ↓
Are its assumptions still fresh?
        ↓
Did it actually finish the job?
        ↓
Can we reproduce the failure?
```

## Design principles

1. **Evidence over confidence** — an agent saying “done” is not proof.
2. **Least capability** — new filesystem, network, subprocess, secret, or environment access should be visible.
3. **Least data** — tools should receive only fields necessary for the declared purpose.
4. **Freshness is explicit** — facts used in plans should have provenance and validity windows.
5. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
6. **Agent-agnostic by default** — skills should be usable from Codex, Claude Code, Cursor, Gemini CLI, MCP-based agents, and custom runtimes.
7. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

## Repository layout

```text
trustforge-skills/
├── action.yml
├── skills/
│   ├── skilldiff/
│   └── commitment-guard/
├── trustforge/
│   ├── ast_detectors.py
│   ├── skilldiff.py
│   └── skilldiff_v03.py
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial SkillDiff evals, language-aware detectors, GitHub Action integrations, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and may eventually execute sandboxed canary tasks. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
