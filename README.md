# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.4.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.4.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

## Current focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.3 released** |
| **DataLease** | Purpose- and destination-bound minimum-necessary data sharing | **v0.4.0 released** |
| **FreshPlan** | Invalidate only plan branches whose source facts have gone stale | **v0.5 MVP** |
| **CommitmentGuard** | Require evidence before an agent can claim completion | MVP |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## FreshPlan v0.5 development

FreshPlan makes freshness explicit for long-running agent plans:

```text
facts + provenance + validity windows
              ↓
        dependency graph
              ↓
         stale detection
              ↓
 selective invalidation
              ↓
       minimal re-plan set
```

FreshPlan stores freshness metadata rather than raw fact values. A stale fact invalidates only the nodes that directly or transitively depend on it; unrelated branches stay valid.

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

Use JSON for orchestration:

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

FreshPlan reports stale facts, provenance, invalidated nodes, root stale-fact causes, unaffected nodes, and a dependency-safe `replan_order`.

## DataLease v0.4

DataLease can sit directly in front of an HTTP transport or MCP tool dispatcher:

```text
Agent payload / tool arguments
        ↓
Declared purpose
        ↓
Destination binding
        ↓
Classifier set
        ↓
allow / redact / deny
        ↓
Minimum-necessary payload
        ↓
HTTP transport / MCP tool
```

It provides default-deny field projection, hard-deny classifier labels, value-free audit evidence, sync/async HTTP and MCP interception, explicit classifier plugins, and measurable classifier regression gates.

### Classifier quality baseline

Primary synthetic 30-case fixture:

```text
precision = 0.913
recall    = 0.875
F1        = 0.894
exact     = 25 / 30
```

A separate multilingual/domain fixture adds Vietnamese email/phone cases, IPv6, credential-path examples, payment/government-id paths, and benign identifier-like values.

These are deterministic regression fixtures, not compliance benchmarks.

### Custom classifier

```python
from trustforge.datalease_classifiers import ClassificationFinding

class EmployeeIdClassifier:
    name = "employee-id-v1"

    def classify(self, path, value):
        if path.endswith("employee_id"):
            return [ClassificationFinding(
                label="org.acme.employee_id",
                detector=self.name,
                confidence=0.98,
            )]
        return []
```

Policies match labels; audit evidence records detector provenance. Built-in label compatibility is documented in [`contracts/datalease-classifier-labels.md`](contracts/datalease-classifier-labels.md).

### Benchmark

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl \
  --min-precision 0.90 \
  --min-recall 0.85
```

### Projection

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

### HTTP interception

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

### MCP interception

```python
from trustforge.datalease_adapters import MCPDataLeaseAdapter

adapter = MCPDataLeaseAdapter.from_policy_file("policy.yaml", call_tool)
result = adapter.call_tool(
    "support.create_ticket",
    purpose="send order summary to support tool",
    arguments=payload,
)
```

## SkillDiff — audit trust-boundary changes

Use the stable GitHub Action line:

```yaml
- uses: actions/checkout@v4
- uses: ptrgiang/trustforge-skills@v0
  with:
    before: fixtures/trusted-skill
    after: skills/candidate-skill
    fail-on: medium
    format: sarif
    report-path: artifacts/skilldiff.sarif
```

For security-sensitive workflows, pin the full release commit SHA instead of the floating `v0` ref.

## Local install

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

## Core idea

```text
SkillDiff → DataLease → FreshPlan → CommitmentGuard → ReproCapsule
```

## Design principles

1. **Evidence over confidence** — an agent saying “done” is not proof.
2. **Least capability** — new filesystem, network, subprocess, secret, or environment access should be visible.
3. **Least data** — tools should receive only fields necessary for the declared purpose.
4. **Destination binding** — minimum data still must not be sent to an unauthorized host/tool.
5. **Measurable classifier quality** — publish regression metrics and known mismatches instead of claiming perfect detection.
6. **Freshness is explicit** — facts used in plans should have provenance and validity windows.
7. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
8. **Agent-agnostic by default** — trust primitives should work across coding agents, MCP runtimes, and custom orchestration.
9. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

## Release and compatibility

- Current development package version: **0.5.0.dev0**.
- Latest stable release: **v0.4.0**.
- Floating stable GitHub Action ref: **`v0`**, still pinned to the v0.4.0 release line while FreshPlan develops on `main`.
- Stable release notes: [`docs/releases/v0.4.0.md`](docs/releases/v0.4.0.md).

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
