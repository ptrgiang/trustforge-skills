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
| **DataLease** | Enforce purpose- and destination-bound minimum-necessary data sharing | **v0.4 development** |
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

DataLease can now sit directly in front of an HTTP transport or MCP tool dispatcher:

```text
Agent payload / tool arguments
        ↓
Declared purpose
        ↓
Destination binding
        ↓
DataLease projection
        ↓
allow / redact / deny
        ↓
HTTP transport / MCP tool
```

A transfer therefore needs both an authorized **purpose** and an authorized **destination**. HTTP adapters bind scheme/host/method; MCP adapters bind tool names or wildcard patterns. The transport is not called when either check fails.

Example interception policy:

```yaml
version: "0.1"
purpose: send order summary to support tool
default_action: deny
hard_deny_classifiers:
  - secret

destinations:
  http:
    schemes: [https]
    hosts: [support.example.com]
    methods: [POST]
  mcp:
    tools: [support.create_ticket]

rules:
  - id: order-summary
    paths:
      - order.id
      - order.status
      - items.*.sku
      - items.*.quantity
    action: allow

  - id: customer-email
    paths: [customer.email]
    classifiers: [pii.email]
    action: redact
    strategy: email_domain
```

Core CLI projection:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

Reference HTTP adapter:

```python
from trustforge.datalease_adapters import HTTPDataLeaseAdapter

adapter = HTTPDataLeaseAdapter.from_policy_file("policy.yaml", transport)
result = adapter.send_json(
    "POST",
    "https://support.example.com/tickets",
    purpose="send order summary to support tool",
    json_body=payload,
)
```

Reference MCP adapter:

```python
from trustforge.datalease_adapters import MCPDataLeaseAdapter

adapter = MCPDataLeaseAdapter.from_policy_file("policy.yaml", call_tool)
result = adapter.call_tool(
    "support.create_ticket",
    purpose="send order summary to support tool",
    arguments=payload,
)
```

Sync and async variants are included. A runnable, network-free demonstration is available at [`examples/datalease/interceptor_demo.py`](examples/datalease/interceptor_demo.py).

The HTTP reference adapter currently projects the JSON body. Transport-owned headers such as authentication are passed through and are outside the application-payload policy surface; callers should not place user data in ungoverned headers. DataLease remains a data-minimization policy engine, not a compliance certification or guarantee about downstream retention/use.

## Local quick start

Development head currently targets `0.4.0.dev1`:

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

## Core idea

```text
SkillDiff → DataLease → FreshPlan → CommitmentGuard → ReproCapsule

Can I trust this skill?
        ↓
What data may it use and where may it send it?
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
4. **Destination binding** — minimum data still must not be sent to an unauthorized host/tool.
5. **Freshness is explicit** — facts used in plans should have provenance and validity windows.
6. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
7. **Agent-agnostic by default** — trust primitives should work across coding agents, MCP runtimes, and custom orchestration.
8. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

## Repository layout

```text
trustforge-skills/
├── action.yml
├── skills/
│   ├── skilldiff/
│   ├── commitment-guard/
│   └── datalease/
├── trustforge/
│   ├── datalease.py
│   └── datalease_adapters.py
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## Release and compatibility

- Latest stable release: **v0.3.0**.
- Floating stable GitHub Action ref: **`v0`**.
- `main` currently contains DataLease v0.4 development work and is not the stable action line.
- Security-sensitive consumers should pin an exact commit SHA.
- Changes are documented in [`CHANGELOG.md`](CHANGELOG.md).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial evals, privacy-policy fixtures, classifier plugins, new language detectors, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and enforces data-minimization policies. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
