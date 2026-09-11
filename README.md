# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.3.0-7c3aed)](docs/releases/v0.3.0.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

The project starts from a simple observation: as agent ecosystems grow, the hard problem is no longer only *what can an agent do?* It is also:

- Did a skill silently gain new capabilities?
- Did its trigger scope quietly become much broader?
- Did the agent satisfy every user constraint before claiming completion?
- Did it expose more data than the task required?
- Is the plan still valid after external facts changed?
- Can a failure be reproduced by another developer?

TrustForge turns those questions into reusable skills, contracts, evidence, and evals.

## Current focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.3 flagship** |
| **CommitmentGuard** | Require evidence for user constraints before an agent can claim completion | MVP |
| **DataLease** | Minimize and gate data shared with tools/APIs | Planned |
| **FreshPlan** | Invalidate plan nodes when facts become stale | Planned |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## Use SkillDiff in GitHub Actions

The fastest way to adopt TrustForge is as a CI gate:

```yaml
- uses: actions/checkout@v4

- name: Audit candidate skill
  uses: ptrgiang/trustforge-skills@v0
  with:
    before: fixtures/trusted-skill
    after: skills/candidate-skill
    fail-on: medium
    format: sarif
    report-path: artifacts/skilldiff.sarif
```

`v0` is the floating stable pre-1.0 action line. For security-sensitive workflows, pin an exact commit SHA. A complete copy-paste workflow is available at [`examples/github-actions/skilldiff.yml`](examples/github-actions/skilldiff.yml).

## Why SkillDiff

A normal file diff answers **what text changed**. SkillDiff tries to answer **what trust assumptions changed**.

```text
files
  ↓
lexical + Python AST capability analysis
  ↓
evidence locations + normalized symbols
  ↓
network domains + dependencies
  ↓
secret-like environment access
  ↓
SKILL.md trigger-scope expansion
  ↓
declared vs observed capability manifest
  ↓
risk explanations + JSON/SARIF
```

Example:

```text
TrustForge SkillDiff
====================
Risk: HIGH

Why:
  - New capabilities detected: environment_read, network, subprocess.
  - Python AST discovered structured behavior missed by lexical matching.
  - New dependency detected: httpx.
  - New secret-like environment reference detected: API_TOKEN.
  - Skill trigger scope appears to have expanded.
  - Observed capabilities are missing from the declared manifest.
```

## Local quick start

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

Human-readable report:

```bash
trustforge skilldiff ./before-skill ./after-skill
```

Machine-readable output:

```bash
trustforge skilldiff ./before-skill ./after-skill --format json
trustforge skilldiff ./before-skill ./after-skill --format sarif > skilldiff.sarif
```

CI threshold:

```bash
trustforge skilldiff ./before-skill ./after-skill --fail-on medium
```

CommitmentGuard:

```bash
trustforge verify examples/refactor-contract.json \
  --evidence examples/refactor-evidence.json
```

## Python AST detector

SkillDiff v0.3 parses candidate Python with the standard-library `ast` module. It does **not** import or execute candidate code.

It resolves common aliases such as:

```python
import subprocess as sp
import requests as rq
from os import getenv as read_env

read_env("DEPLOY_TOKEN")
rq.post(endpoint, json=payload)
sp.run(["echo", "done"], check=True)
```

It also distinguishes read/write modes for `open()` and attaches structured provenance such as detector, symbol, source line, and confidence.

## Capability manifests

A skill can declare expected capabilities in `trustforge.json`:

```json
{
  "capabilities": ["network", "filesystem_read"]
}
```

SkillDiff compares the declaration with capabilities observed by its static detectors and surfaces mismatches for review.

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
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## Release and compatibility

- Current package/action line: **v0.3.0**.
- Floating stable GitHub Action ref: **`v0`**.
- Security-sensitive consumers should pin an exact commit SHA.
- Changes are documented in [`CHANGELOG.md`](CHANGELOG.md).
- v0.3.0 notes: [`docs/releases/v0.3.0.md`](docs/releases/v0.3.0.md).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial SkillDiff evals, new language detectors, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and may eventually execute sandboxed canary tasks. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
