# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.7.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.7.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Don't just let agents act. Make them prove it.**

TrustForge is an open-source set of trust primitives for autonomous AI agents.

**As agents get more capable, who checks what they changed, what data they send, whether their plan is still based on fresh evidence, and whether "done" is actually true?**

TrustForge does not try to be another agent framework. It sits around agent workflows and makes important trust boundaries visible, testable, and auditable.

## What is in the repo today

| Primitive | What it does | Status |
| --- | --- | --- |
| **SkillDiff** | Detects trust-boundary changes between skill versions | **Released** |
| **DataLease** | Sends only the minimum necessary data to approved destinations | **Released** |
| **FreshPlan** | Detects aging evidence and re-plans only affected branches | **Released** |
| **CommitmentGuard** | Requires evidence before completion claims | **Released** |
| **ReproCapsule** | Packages failures, verifies replay, exports/replays container contexts, and gates trace redaction | **Released** |

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

## CommitmentGuard v0.7.0

CommitmentGuard turns completion claims into explicit contracts that can be checked against structured evidence.

```text
user commitments
      ↓
required / optional contract
      ↓
evidence collection adapters
      ↓
evidence observations + provenance
      ↓
freshness + source trust policy
      ↓
PASS / FAIL / UNKNOWN / WAIVED
      ↓
verified_complete / partial / not_verified
```

### Verify completion

```bash
trustforge verify \
  examples/commitmentguard/release-contract.json \
  --evidence examples/commitmentguard/release-evidence.json \
  --as-of "2026-09-11T14:01:00Z"
```

v0.7.0 adds:

- contract, evidence, and report schemas v0.2;
- required vs optional commitments;
- `verified_complete | partial | not_verified` completion states;
- structured waivers with expiry;
- deterministic `--as-of` evaluation;
- evidence freshness via `max_age_seconds`;
- source trust via `allowed_source_kinds`;
- fail-closed stale/future/untrusted evidence handling;
- generic command exit-code evidence;
- dedicated pytest evidence;
- GitHub Actions runtime evidence without API tokens/network calls;
- JSON artifact field evidence with SHA-256 provenance;
- exact package-manifest snapshot evidence;
- OpenAPI path+method removal evidence;
- evidence-bundle merge with duplicate-key rejection;
- backward compatibility with legacy nested evidence documents.

### Command evidence

```bash
trustforge evidence command \
  --key tests.passed \
  --observed-at "2026-09-11T14:30:00Z" \
  -- python -m unittest discover -s tests
```

Exit code `0` becomes `true`; nonzero becomes `false`. Raw argv/stdout/stderr are not copied into the evidence bundle.

### Pytest evidence

```bash
trustforge evidence pytest \
  --key tests.passed \
  --observed-at "2026-09-11T14:45:00Z" \
  -- tests -q
```

Pytest remains an external workflow dependency. The adapter records normalized process provenance without copying raw pytest arguments or output.

### GitHub Actions evidence

```yaml
- name: Emit CI evidence
  if: always()
  run: |
    trustforge evidence github-actions \
      --key ci.passed \
      --conclusion "${{ job.status }}" \
      > ci-evidence.json
```

This adapter requires `GITHUB_ACTIONS=true`, records a whitelist of non-secret runtime metadata, does not read `GITHUB_TOKEN`, and makes no GitHub API call.

### JSON artifact evidence

```bash
trustforge evidence json-artifact \
  --key tests.coverage \
  --input coverage.json \
  --value-path totals.percent
```

### Package-manifest evidence

```bash
trustforge evidence package-manifest \
  --input pyproject.toml
```

The observation value is the exact SHA-256 digest of the manifest. It proves which bytes were read, not that the dependencies are safe.

### API-diff evidence

```bash
trustforge evidence api-diff \
  --before openapi-before.json \
  --after openapi-after.json
```

The first API-diff contract checks OpenAPI-like JSON path+HTTP-method removals. It returns `true` when no operation was removed. Provenance stores document hashes and counts rather than endpoint names. It does **not** claim to detect schema-level or semantic breaking changes.

Provenance is metadata, not cryptographic attestation. Hashes identify exact bytes, process exit status identifies an observed process result, and GitHub Actions metadata identifies runtime context; none of these alone proves the source was trustworthy or the check was sufficient for the real-world requirement.

Release notes: [`docs/releases/v0.7.0.md`](docs/releases/v0.7.0.md)

## ReproCapsule v0.6.0

Build a portable failure capsule:

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule
```

Verify or replay it:

```bash
trustforge reprocapsule replay \
  --capsule .artifacts/reprocapsule \
  --execute \
  --fail-on-divergence
```

Container replay is also available through `reprocapsule export-container` and `reprocapsule replay-container`. Host/container replay are not claimed to be complete security sandboxes.

Release notes: [`docs/releases/v0.6.0.md`](docs/releases/v0.6.0.md)

## FreshPlan v0.5.0

FreshPlan supports provenance/freshness metadata, TTL/validity windows, named policies, selective invalidation, value-free refresh requests, trusted refresh adapters, replacement semantics, minimal plan patches, and deterministic large-graph regression tests.

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
- Evidence provenance does not prove source authenticity.
- Artifact/package hashes do not prove the producer or dependencies were trustworthy.
- Command or pytest exit-code evidence does not prove the selected checks tested the right requirement.
- GitHub Actions environment metadata is useful provenance but is not a signed attestation from GitHub.
- API-diff v0.7 only checks path+method removals, not arbitrary schema/semantic compatibility.
- Redaction reduces disclosure but does not prove arbitrary secrets can never appear.
- ReproCapsule host/container replay is not a complete security sandbox.

The goal is useful infrastructure with measurable boundaries, not perfect detection or novelty marketing.

## Build in public

TrustForge is still pre-1.0 and is being developed in the open. The repository includes implementation, eval fixtures, known limitations, release checklists, benchmark gates, and design tradeoffs as they evolve.

The latest stable release is **v0.7.0**. Future development continues on `main`; the floating stable `v0` ref now points to the verified v0.7.0 release commit.

## Design principles

1. **Evidence over confidence.** A completion claim is not proof.
2. **Least capability.** New powers should be visible.
3. **Least data.** Tools should receive only what the purpose requires.
4. **Destination binding.** Minimum data still should not go to the wrong place.
5. **Freshness is explicit.** Plans and completion evidence should know when their facts are aging.
6. **Conservative recovery.** Unknown evidence should not silently become proof.
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

- Package/runtime version: **0.7.0**
- Latest stable release: **v0.7.0**
- Floating stable GitHub Action ref: **`v0`**, pinned to the verified v0.7.0 release commit
- License: Apache-2.0

## Contributing

Issues, concrete failure cases, benchmark ideas, adapters, and focused PRs are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
