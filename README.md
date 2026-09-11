# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.3.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.3.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

The project focuses on trust questions that become important once agents can install skills, call tools, send data, and claim work is complete:

- Did a skill silently gain new capabilities?
- Did its trigger scope become broader?
- Did the agent expose more data than the task required?
- Was that data sent to an authorized destination?
- Did the agent satisfy every user constraint before claiming completion?
- Can a failure be reproduced by another developer?

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

`v0` is the floating stable pre-1.0 action line. Security-sensitive workflows should pin an exact commit SHA.

## DataLease — share only what the task needs

DataLease can sit directly in front of an HTTP transport or MCP tool dispatcher:

```text
Agent payload / tool arguments
        ↓
Declared purpose
        ↓
Destination binding
        ↓
Field classifiers
        ↓
allow / redact / deny
        ↓
Minimum-necessary payload
        ↓
HTTP transport / MCP tool
```

A transfer therefore needs an authorized **purpose**, authorized **destination**, and field-level policy decision.

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

Core projection:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

Reference HTTP interception:

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

Reference MCP interception:

```python
from trustforge.datalease_adapters import MCPDataLeaseAdapter

adapter = MCPDataLeaseAdapter.from_policy_file("policy.yaml", call_tool)
result = adapter.call_tool(
    "support.create_ticket",
    purpose="send order summary to support tool",
    arguments=payload,
)
```

Sync and async variants are included. A runnable network-free demo lives at [`examples/datalease/interceptor_demo.py`](examples/datalease/interceptor_demo.py).

## Pluggable DataLease classifiers

Applications can supply trusted Python classifier objects without changing the serialized policy format or dynamically importing untrusted plugin strings.

```python
from trustforge.datalease import apply_policy
from trustforge.datalease_classifiers import ClassificationFinding

class EmployeeIdClassifier:
    name = "employee-id-v1"

    def classify(self, path, value):
        if path.endswith("employee_id"):
            return [ClassificationFinding(
                label="sensitivity.internal_id",
                detector=self.name,
                confidence=0.98,
                reason="Organization-specific employee identifier.",
            )]
        return []

report = apply_policy(
    policy,
    purpose,
    payload,
    classifiers=[EmployeeIdClassifier()],
)
```

Custom findings can participate in normal classifier rules or `hard_deny_classifiers`. HTTP/MCP adapters accept the same `classifiers=[...]` argument. Classifier failures fail closed with `DataLeaseError`.

Audit records expose classifier provenance such as label, detector, confidence, and reason, but never copy the original leaf value into classifier evidence.

A complete example is available at [`examples/datalease/custom_classifier.py`](examples/datalease/custom_classifier.py).

## Classifier benchmark

TrustForge includes a small deterministic regression dataset with positive, negative, and adversarial classifier cases:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl
```

Current built-in baseline on the 30-case synthetic fixture:

```text
precision:   0.913
recall:      0.875
F1:          0.894
exact match: 25 / 30
```

CI enforces minimum micro precision `0.90` and recall `0.85` so detector changes cannot silently regress below the documented baseline.

The fixture intentionally contains known mismatches, including metadata fields such as `email_verified`/`email_domain` and sensitive values embedded in free text. It is a regression suite, **not** evidence of production-grade PII detection or compliance certification. See [`evals/datalease/README.md`](evals/datalease/README.md).

## Local quick start

Development head currently targets `0.4.0.dev2`:

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

DataLease benchmark gate:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl \
  --min-precision 0.90 \
  --min-recall 0.85
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
5. **Measured limitations** — heuristics should have regression datasets and published failure cases.
6. **Freshness is explicit** — facts used in plans should have provenance and validity windows.
7. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
8. **Agent-agnostic by default** — trust primitives should work across coding agents, MCP runtimes, and custom orchestration.
9. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

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
│   ├── datalease_adapters.py
│   ├── datalease_classifiers.py
│   └── datalease_eval.py
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## Release and compatibility

- Latest stable release: **v0.3.0**.
- Floating stable GitHub Action ref: **`v0`**.
- `main` contains DataLease v0.4 development work and is not the stable action line.
- Security-sensitive consumers should pin an exact commit SHA.
- Changes are documented in [`CHANGELOG.md`](CHANGELOG.md).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are especially welcome for adversarial evals, multilingual privacy fixtures, classifier plugins, new language detectors, agent-runtime integrations, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and enforces data-minimization policies. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
