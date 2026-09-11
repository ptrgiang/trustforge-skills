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

TrustForge turns those questions into reusable skills, contracts, evidence, and evals.

## Current focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.2 flagship** |
| **CommitmentGuard** | Require evidence for user constraints before an agent can claim completion | MVP |
| **DataLease** | Minimize and gate data shared with tools/APIs | Planned |
| **FreshPlan** | Invalidate plan nodes when facts become stale | Planned |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## Why SkillDiff

A normal file diff answers **what text changed**. SkillDiff tries to answer **what trust assumptions changed**.

It currently checks:

```text
files
  ↓
capabilities + evidence locations
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
  - New dependency detected: httpx.
  - New secret-like environment reference detected: API_TOKEN.
  - Skill trigger scope appears to have expanded.
  - Observed capabilities are missing from the declared manifest.
```

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

Run CommitmentGuard:

```bash
trustforge verify examples/refactor-contract.json \
  --evidence examples/refactor-evidence.json
```

## Capability manifests

A skill can declare expected capabilities in `trustforge.json`:

```json
{
  "capabilities": ["network", "filesystem_read"]
}
```

SkillDiff compares the declaration with capabilities observed by the static scanner and surfaces mismatches for review.

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

## What makes a TrustForge skill?

A TrustForge skill should define:

- a narrow trust/reliability problem;
- explicit inputs and outputs;
- capabilities and side effects;
- machine-checkable evidence where possible;
- failure modes and refusal conditions;
- eval cases demonstrating both success and failure.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial SkillDiff evals, new language detectors, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and may eventually execute sandboxed canary tasks. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
