# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.3.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.3.0)
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
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.3 released** |
| **DataLease** | Enforce purpose-bound minimum-necessary data sharing | **v0.4 MVP on `main`** |
| **CommitmentGuard** | Require evidence before an agent can claim completion | MVP |
| **FreshPlan** | Invalidate plan nodes when facts become stale | Planned |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## SkillDiff — audit trust-boundary changes

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

Use the released GitHub Action:

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

`v0` is the floating stable pre-1.0 action line. For security-sensitive workflows, pin an exact commit SHA. A complete workflow is available at [`examples/github-actions/skilldiff.yml`](examples/github-actions/skilldiff.yml).

## DataLease — share only what the task needs

DataLease sits immediately before a tool/API/MCP/connector boundary:

```text
Agent payload
    ↓
Declared purpose
    ↓
DataLease policy
    ↓
Field classification
    ↓
allow / redact / deny
    ↓
Minimum-necessary payload + audit trail
```

Example policy:

```yaml
version: "0.1"
purpose: send order summary to support tool
default_action: deny
hard_deny_classifiers:
  - secret

rules:
  - id: order-summary
    paths:
      - order.id
      - order.status
      - items.*.sku
      - items.*.quantity
    action: allow

  - id: customer-email
    paths:
      - customer.email
    classifiers:
      - pii.email
    action: redact
    strategy: email_domain
```

Apply it:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json
```

Pipe only the projected payload to another tool:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

The MVP provides exact purpose binding, nested wildcard paths, `allow`/`redact`/`deny`, basic PII/secret classifiers, hard-deny classifiers with `secret` enabled by default, value-free audit records, JSON/YAML policies, and redaction strategies `mask`, `null`, `last4`, and `email_domain`.

DataLease is a data-minimization policy engine, not a compliance certification and not a guarantee about downstream retention or use.

## Local quick start

Development head currently targets `0.4.0.dev0`:

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

SkillDiff:

```bash
trustforge skilldiff ./before-skill ./after-skill
trustforge skilldiff ./before-skill ./after-skill --format json
trustforge skilldiff ./before-skill ./after-skill --format sarif > skilldiff.sarif
trustforge skilldiff ./before-skill ./after-skill --fail-on medium
```

CommitmentGuard:

```bash
trustforge verify examples/refactor-contract.json \
  --evidence examples/refactor-evidence.json
```

DataLease:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.json \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only \
  --audit-output .artifacts/datalease-audit.json
```

## Python AST detector

SkillDiff v0.3 parses candidate Python with the standard-library `ast` module. It does **not** import or execute candidate code. It resolves common aliases and distinguishes read/write modes for `open()`, attaching detector, symbol, source line, and confidence to structured evidence.

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
│   ├── commitment-guard/
│   └── datalease/
├── trustforge/
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## Release and compatibility

- Latest stable release: **v0.3.0**.
- Floating stable GitHub Action ref: **`v0`**.
- `main` currently contains the DataLease v0.4 development MVP.
- Security-sensitive consumers should pin an exact commit SHA.
- Changes are documented in [`CHANGELOG.md`](CHANGELOG.md).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial evals, privacy-policy fixtures, new language detectors, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and enforces data-minimization policies. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
