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

## The problem

Agents can already:

- read and write files;
- call APIs and tools;
- use credentials;
- send structured data to external systems;
- keep long-running plans alive;
- claim that a task is complete.

Those abilities are useful. They also create a new layer of engineering problems.

```text
Agent changes a skill
        ↓
Did its capabilities expand?
        ↓
Agent sends data to a tool
        ↓
Did it send more than the task required?
        ↓
Agent keeps executing a plan
        ↓
Is the evidence behind that plan still fresh?
        ↓
Agent says "done"
        ↓
What evidence proves it?
```

TrustForge is being built around those questions.

## What is in the repo today

```text
                       TrustForge
                           │
          ┌────────────────┼────────────────┐
          │                │                │
      SkillDiff        DataLease        FreshPlan
          │                │                │
  capability drift   outbound data    stale evidence
  trust boundaries   minimization     selective replan
          │                │                │
          └────────────────┼────────────────┘
                           │
             CommitmentGuard + ReproCapsule
                  proof + reproducibility
```

| Primitive | What it does | Status |
| --- | --- | --- |
| **SkillDiff** | Detects trust-boundary changes between skill versions | Released |
| **DataLease** | Sends only the minimum necessary data to approved destinations | Released |
| **FreshPlan** | Detects aging evidence and re-plans only affected branches | **v0.5.0** |
| **CommitmentGuard** | Requires evidence before completion claims | MVP |
| **ReproCapsule** | Packages failures into portable, sanitized reproduction artifacts | **v0.6 in development** |

## Who this is for

TrustForge is most useful if you are building:

- autonomous or semi-autonomous agents;
- coding agents;
- MCP servers and tool runtimes;
- long-running agent workflows;
- internal AI automation that touches real systems;
- evaluation, safety, reliability, or platform infrastructure around agents.

If your agent can change code, call tools, move data, or act for a long time, these are the kinds of boundaries TrustForge is trying to make explicit.

## Start here

Clone and install:

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills
pip install -e .
```

### 1. Inspect a skill change

```bash
trustforge skilldiff \
  evals/skilldiff/python-ast-alias/before \
  evals/skilldiff/python-ast-alias/after \
  --format text
```

SkillDiff looks for changes such as new network access, subprocess execution, environment reads, filesystem writes, dynamic execution, dependency changes, and secret-like references.

### 2. Minimize data before a tool call

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

DataLease applies purpose binding, destination binding, allow/redact/deny rules, hard-deny classifiers, and value-free audit evidence.

### 3. Check whether a plan is still based on fresh evidence

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

FreshPlan models facts as `fresh`, `refresh_due`, or `stale`. Only stale evidence invalidates dependent nodes, so unrelated branches stay valid.

### 4. Package a failure without packaging secrets

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule
```

The v0.6 MVP writes a portable manifest, hashes/copies explicitly listed failing inputs, fingerprints the runtime environment, and sanitizes the supplied failure trace. Raw environment values are not copied, secret-like command arguments are rejected, and the build step does not execute the failing command.

## ReproCapsule v0.6 development

The current development line is focused on a problem that shows up constantly in coding-agent workflows: a failure happened on one machine, but the next developer or agent does not have enough trustworthy context to reproduce it.

Current build flow:

```text
failure context
      ↓
explicit build spec
      ↓
path + secret safety checks
      ↓
input hashes / safe copies
      ↓
sanitized trace
      ↓
environment fingerprint
      ↓
portable reprocapsule.json
```

The MVP deliberately does **not** replay commands yet. Replay verification comes next, after integrity and safety checks are defined clearly.

See [`skills/reprocapsule/SKILL.md`](skills/reprocapsule/SKILL.md) and [`ROADMAP.md`](ROADMAP.md).

## FreshPlan v0.5.0

The latest stable release focuses on long-running plans that depend on time-sensitive evidence.

FreshPlan supports provenance and freshness metadata, TTL/validity windows, named freshness policies, selective invalidation, value-free refresh requests, trusted refresh adapters, replacement semantics, minimal plan patches, and deterministic large-graph regression tests.

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

This project is intentionally conservative about claims.

- Classifier benchmarks are regression fixtures, not compliance certifications.
- Performance gates are regression alarms, not production SLAs.
- Freshness policies cannot prove that a domain-specific TTL is correct.
- Static capability detection cannot prove runtime behavior.
- Redaction reduces disclosure but does not automatically make data anonymous.
- ReproCapsule trace sanitization is a defensive baseline, not a proof that arbitrary secrets can never appear.

The goal is useful infrastructure with measurable boundaries, not perfect detection or novelty marketing.

## Build in public

TrustForge is still pre-1.0 and is being developed in the open.

The repository includes the implementation, eval fixtures, known limitations, release checklists, benchmark gates, and design tradeoffs as they evolve.

The active milestone is **ReproCapsule v0.6**. The first MVP packages failure metadata safely; replay verification and container/devcontainer export are next.

If you are working on agent infrastructure, feedback is useful even if the answer is "this would not fit my stack." Open an issue with a concrete workflow or failure mode.

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

- Development package version on `main`: **0.6.0.dev0**
- Latest stable release: **v0.5.0**
- Floating stable GitHub Action ref: **`v0`**
- License: Apache-2.0

## Contributing

Issues, concrete failure cases, benchmark ideas, adapters, and focused PRs are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
