# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.5.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.5.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge is an open-source set of trust primitives for autonomous AI agents.

It started from a simple question:

**As agents get more capable, who checks what they changed, what data they send, whether their plan is still based on fresh evidence, and whether "done" is actually true?**

TrustForge does not try to be another agent framework. It sits around agent workflows and makes important trust boundaries visible, testable, and auditable.

## What is in the repo today

| Primitive | What it does | Status |
| --- | --- | --- |
| **SkillDiff** | Detects trust-boundary changes between skill versions | Released |
| **DataLease** | Sends only the minimum necessary data to approved destinations | Released |
| **FreshPlan** | Detects aging evidence and re-plans only affected branches | **v0.5.0** |
| **CommitmentGuard** | Requires evidence before completion claims | MVP |
| **ReproCapsule** | Packages failures, verifies replay, exports container contexts, and gates trace redaction | **v0.6 in development** |

## Who this is for

TrustForge is most useful if you are building autonomous or semi-autonomous agents, coding agents, MCP servers/tool runtimes, long-running workflows, internal AI automation, or reliability/evaluation infrastructure around agents.

## Start here

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

### Inspect a skill change

```bash
trustforge skilldiff \
  evals/skilldiff/python-ast-alias/before \
  evals/skilldiff/python-ast-alias/after \
  --format text
```

### Minimize data before a tool call

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

### Check whether a plan is still based on fresh evidence

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

### Package, verify, and export a failure

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule
```

```bash
trustforge reprocapsule replay \
  --capsule .artifacts/reprocapsule \
  --execute \
  --fail-on-divergence
```

```bash
trustforge reprocapsule export-container \
  --capsule .artifacts/reprocapsule \
  --output .artifacts/reprocapsule-container
```

### Gate trace redaction

```bash
trustforge reprocapsule benchmark-redaction \
  --dataset evals/reprocapsule/redaction-benchmark.jsonl \
  --min-secret-recall 1.0 \
  --min-clean-specificity 1.0
```

The benchmark uses synthetic adversarial traces. `secret_recall` measures how many secret-bearing cases are fully sanitized. `clean_specificity` measures how many clean near-miss cases remain unchanged. Reports identify failed case IDs without echoing the synthetic secret values.

## ReproCapsule v0.6 development

```text
failure context
      ↓
explicit build spec
      ↓
path + secret safety checks
      ↓
input hashes / safe copies
      ↓
sanitized trace + runtime fingerprint
      ↓
portable capsule
      ↓
integrity preflight
      ↓
explicit replay gate
      ↓
reproduced / diverged / blocked
      ↓
verified Docker/devcontainer export
      ↓
adversarial redaction regression gate
```

The generated container context uses a non-root runtime user and derives a Python major/minor base image from the captured runtime fingerprint. It is a portability aid, not a guarantee that all native/system dependencies are reproduced.

Important boundary: neither the temporary replay workspace nor the generated container definition is claimed to be a complete security sandbox. Untrusted capsules still require hardened isolation and an appropriate container/runtime policy.

Next on the v0.6 line: containerized replay isolation and release hardening.

See [`skills/reprocapsule/SKILL.md`](skills/reprocapsule/SKILL.md) and [`ROADMAP.md`](ROADMAP.md).

## FreshPlan v0.5.0

The latest stable release focuses on long-running plans that depend on time-sensitive evidence. FreshPlan supports provenance/freshness metadata, TTL/validity windows, named policies, selective invalidation, value-free refresh requests, trusted refresh adapters, replacement semantics, minimal plan patches, and deterministic large-graph regression tests.

Release notes: [`docs/releases/v0.5.0.md`](docs/releases/v0.5.0.md)

## Use SkillDiff in GitHub Actions

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

## What TrustForge does not claim

- Classifier and redaction benchmarks are regression fixtures, not compliance certifications.
- Performance gates are regression alarms, not production SLAs.
- Freshness policies cannot prove that a domain-specific TTL is correct.
- Static capability detection cannot prove runtime behavior.
- Redaction reduces disclosure but does not prove arbitrary secrets can never appear.
- ReproCapsule replay and generated container definitions are not complete security sandboxes.
- Container export does not yet capture arbitrary OS/native dependency locks.

The goal is useful infrastructure with measurable boundaries, not perfect detection or novelty marketing.

## Build in public

TrustForge is still pre-1.0 and is being developed in the open. The repository includes implementation, eval fixtures, known limitations, release checklists, benchmark gates, and design tradeoffs as they evolve.

The active milestone is **ReproCapsule v0.6**. Safe packaging, integrity-gated replay, container export, and adversarial redaction regression gates are now implemented.

## Design principles

1. **Evidence over confidence.** A completion claim is not proof.
2. **Least capability.** New powers should be visible.
3. **Least data.** Tools should receive only what the purpose requires.
4. **Destination binding.** Minimum data still should not go to the wrong place.
5. **Freshness is explicit.** Plans should know when their evidence is aging.
6. **Conservative recovery.** Unknown changes should trigger re-planning.
7. **Failures should travel.** Reproduction should not depend on the original machine.
8. **Agent-agnostic by default.** Trust primitives should work across runtimes.
9. **No unverifiable novelty claims.** Measure the gap instead.

## Project map

- [`skills/`](skills/) skill specifications
- [`contracts/`](contracts/) machine-readable contracts
- [`evals/`](evals/) adversarial and regression fixtures
- [`examples/`](examples/) runnable examples
- [`docs/releases/`](docs/releases/) release notes and release records
- [`ROADMAP.md`](ROADMAP.md) development roadmap
- [`CONTRIBUTING.md`](CONTRIBUTING.md) contribution guide
- [`SECURITY.md`](SECURITY.md) security policy

## Release and compatibility

- Development package version on `main`: **0.6.0.dev3**
- Latest stable release: **v0.5.0**
- Floating stable GitHub Action ref: **`v0`**
- License: Apache-2.0

## Contributing

Issues, concrete failure cases, benchmark ideas, adapters, and focused PRs are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
