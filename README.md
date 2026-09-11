# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.8.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.8.0)
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

## CommitmentGuard v0.8.0

CommitmentGuard turns completion claims into explicit contracts that can be checked against structured evidence.

v0.8 adds an optional signed-evidence layer on top of the v0.7 completion-contract model:

```text
user commitments
      ↓
required / optional contract
      ↓
evidence collection adapters
      ↓
evidence observations + provenance
      ↓
optional Ed25519 attestation
      ↓
issuer + key policy + trust registry
      ↓
freshness / source / signature checks
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

### Require signed evidence

A contract can require an attestation and restrict acceptable signer identities:

```json
{
  "key": "ci.passed",
  "truthy": true,
  "require_attestation": true,
  "allowed_attestation_issuers": ["release-ci"],
  "allowed_attestation_key_ids": ["2026-09"]
}
```

Trusted public keys are supplied separately through a trust registry, so the completion contract cannot make an arbitrary embedded key trusted.

### Sign an evidence observation

```bash
trustforge evidence sign \
  --input evidence.json \
  --key ci.passed \
  --private-key signer.pem \
  --issuer release-ci \
  --key-id 2026-09 \
  --issued-at 2026-09-12T00:00:00Z \
  --expires-at 2026-09-13T00:00:00Z \
  > signed-evidence.json
```

### Verify a signed observation

```bash
trustforge evidence verify-attestation \
  --input signed-evidence.json \
  --key ci.passed \
  --trust-registry trust-registry.json \
  --as-of 2026-09-12T01:00:00Z
```

### Require the signature in the completion gate

```bash
trustforge verify contract.json \
  --evidence signed-evidence.json \
  --trust-registry trust-registry.json \
  --as-of 2026-09-12T01:00:00Z
```

v0.8 adds:

- Ed25519 attestation schema v0.1;
- canonical JSON hashing for observation values and provenance;
- signature binding to observation key, issuer, key ID, issue time, and optional expiry;
- `require_attestation` and issuer/key allow-list policies;
- external public-key trust registry;
- fail-closed handling for missing, malformed, invalid-signature, tampered, future-dated, expired, unknown-key, and disallowed signer evidence;
- trust-registry path confinement;
- signed-evidence adversarial fixtures;
- direct sign/verify CLI flows;
- compatibility with the v0.7 contract/evidence/report schema line.

The v0.7 evidence adapters remain available: command, pytest, GitHub Actions, JSON artifact, package manifest, and narrow OpenAPI path+method removal evidence.

A valid signature proves that the holder of the corresponding private key signed the canonical payload. It does **not** prove that the signer collected correct evidence, that the signer was uncompromised, that the evidence was sufficient, or that the trust registry itself was distributed securely.

TrustForge v0.8 is therefore a signed-evidence primitive, not a complete PKI system. Cloud KMS/HSM integration, certificate chains, transparency logs, remote signing, and automatic revocation distribution remain out of scope for this release.

Release notes: [`docs/releases/v0.8.0.md`](docs/releases/v0.8.0.md)

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
- Unsigned evidence provenance does not prove source authenticity.
- A valid attestation does not prove the signer or underlying evidence source was trustworthy.
- Artifact/package hashes do not prove the producer or dependencies were trustworthy.
- Command or pytest exit-code evidence does not prove the selected checks tested the right requirement.
- GitHub Actions environment metadata is useful provenance but is not itself a signed attestation from GitHub.
- API-diff only checks path+method removals, not arbitrary schema/semantic compatibility.
- Redaction reduces disclosure but does not prove arbitrary secrets can never appear.
- ReproCapsule host/container replay is not a complete security sandbox.

The goal is useful infrastructure with measurable boundaries, not perfect detection or novelty marketing.

## Build in public

TrustForge is still pre-1.0 and is being developed in the open. The repository includes implementation, eval fixtures, known limitations, release checklists, benchmark gates, and design tradeoffs as they evolve.

The latest stable release is **v0.8.0**. Future development continues on `main`; the floating stable `v0` ref points to the verified v0.8.0 release commit.

## Design principles

1. **Evidence over confidence.** A completion claim is not proof.
2. **Least capability.** New powers should be visible.
3. **Least data.** Tools should receive only what the purpose requires.
4. **Destination binding.** Minimum data still should not go to the wrong place.
5. **Freshness is explicit.** Plans and completion evidence should know when their facts are aging.
6. **Conservative recovery.** Unknown evidence should not silently become proof.
7. **Failures should travel.** Reproduction should not depend on the original machine.
8. **Trust roots stay external.** A policy should not be able to declare its own arbitrary signer trusted.
9. **Agent-agnostic by default.** Trust primitives should work across runtimes.
10. **No unverifiable novelty claims.** Measure the gap instead.

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

- Package/runtime version: **0.8.0**
- Latest stable release: **v0.8.0**
- Floating stable GitHub Action ref: **`v0`**, pinned to the verified v0.8.0 release commit
- License: Apache-2.0

## Contributing

Issues, concrete failure cases, benchmark ideas, adapters, and focused PRs are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
