# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.5.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.5.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

## Current focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect trust-boundary changes between skill versions | **v0.3 released** |
| **DataLease** | Purpose- and destination-bound minimum-necessary data sharing | **v0.4 released** |
| **FreshPlan** | Refresh aging evidence and re-plan only affected branches | **v0.5.0** |
| **CommitmentGuard** | Require evidence before an agent can claim completion | MVP |
| **ReproCapsule** | Package failures into reproducible environments | Planned |

## FreshPlan v0.5

FreshPlan makes freshness explicit for long-running agent plans:

```text
facts + provenance + freshness policy
              ↓
        dependency graph
              ↓
   fresh / refresh_due / stale
              ↓
   value-free refresh request
              ↓
      replacement evidence
              ↓
  blocked / replan / resume patch
```

FreshPlan reports freshness metadata rather than raw fact values. A stale fact invalidates only the nodes that directly or transitively depend on it; unrelated branches stay valid.

### Check freshness

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

### Named freshness policies

Facts can reuse plan-level policies instead of repeating TTL values:

```yaml
freshness_policies:
  volatile:
    refresh_after_seconds: 300
    expire_after_seconds: 900

facts:
  - id: inventory
    observed_at: "2026-09-11T09:20:00Z"
    freshness_policy: volatile
    provenance:
      source: inventory-api
```

`refresh_after_seconds` is a soft boundary. When it is reached, the fact becomes `refresh_due` and FreshPlan recommends a refresh without invalidating the plan. `expire_after_seconds` is the hard boundary; only hard-stale facts invalidate dependent nodes. Explicit `ttl_seconds` or `valid_until` can still be used and act as additional hard bounds, with the earliest hard expiry winning.

### Emit refresh requests

Facts can declare an adapter name and opaque refresh reference:

```yaml
refresh:
  adapter: inventory-api
  reference: inventory:SKU-1
```

Generate a value-free request report:

```bash
trustforge freshplan requests \
  --plan examples/freshplan/refreshable-order.yaml \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

Refresh requests are emitted for both `refresh_due` and `stale` facts. The CLI does not dynamically import or execute adapters. Application code registers trusted adapter objects explicitly.

### Apply replacement evidence and emit a minimal patch

```bash
trustforge freshplan patch \
  --plan examples/freshplan/refreshable-order.yaml \
  --evidence examples/freshplan/replacement-evidence.json \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

Each replacement must explicitly declare:

```text
change = changed | unchanged | unknown
```

`changed` and `unknown` conservatively re-plan the affected branch. `unchanged` can resume the existing branch after freshness is restored. If replacement evidence is still stale, the branch remains blocked.

The control-plane patch uses only three node operations:

```text
blocked  → evidence is still stale; do not continue
replan   → replacement changed or change is unknown
resume   → freshness restored and replacement is explicitly unchanged
```

Policy-bound facts may preserve their existing named freshness policy when replacement evidence omits a new TTL/absolute expiry.

### Python adapter API

```python
from trustforge.freshplan_refresh import CallableRefreshAdapter, refresh_with_adapters

adapter = CallableRefreshAdapter("inventory-api", refresh_inventory)
patch = refresh_with_adapters(
    plan,
    {"inventory-api": adapter},
    as_of="2026-09-11T09:30:00Z",
)
```

Adapter requests contain freshness/provenance metadata and refresh references, not raw fact values. Adapter failures, missing registrations, malformed evidence, or evidence for the wrong fact fail closed.

### Large-graph benchmark

FreshPlan ships a deterministic synthetic parallel-chain generator so graph evaluation cost is measurable in CI:

```bash
trustforge freshplan benchmark \
  --nodes 1000 5000 10000 \
  --repeats 3 \
  --json
```

A regression gate can cap the largest case:

```bash
trustforge freshplan benchmark \
  --nodes 1000 5000 10000 \
  --repeats 2 \
  --max-median-ms 5000
```

The benchmark reports nodes, facts, edges, median/min/max runtime, throughput, stale facts, and invalidated nodes. The CI threshold is deliberately generous and is a regression alarm, not a universal performance guarantee or SLA.

Contracts:

- [`contracts/freshplan.schema.json`](contracts/freshplan.schema.json)
- [`contracts/freshplan-refresh-request.schema.json`](contracts/freshplan-refresh-request.schema.json)
- [`contracts/freshplan-replacement.schema.json`](contracts/freshplan-replacement.schema.json)
- [`contracts/freshplan-patch.schema.json`](contracts/freshplan-patch.schema.json)

Release notes: [`docs/releases/v0.5.0.md`](docs/releases/v0.5.0.md).

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
7. **Refresh before invalidation when possible** — soft freshness windows can trigger proactive evidence renewal without discarding still-valid plan branches.
8. **Conservative recovery** — unknown replacement changes should trigger re-planning rather than silently resuming stale reasoning.
9. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
10. **Agent-agnostic by default** — trust primitives should work across coding agents, MCP runtimes, and custom orchestration.
11. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

## Release and compatibility

- Current package version: **0.5.0**.
- Latest stable release: **v0.5.0**.
- Floating stable GitHub Action ref: **`v0`**; it is advanced only after a release tag and GitHub Release are verified.
- FreshPlan contracts remain on schema version **`0.1`** for the v0.5.0 release line.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
