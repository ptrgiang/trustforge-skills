# TrustForge Skills

[![CI](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ptrgiang/trustforge-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/badge/release-v0.6.0-7c3aed)](https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.6.0)
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
| **CommitmentGuard** | Requires evidence before completion claims | **v0.7 in development** |
| **ReproCapsule** | Packages failures, verifies replay, exports/replays container contexts, and gates trace redaction | **v0.6.0** |

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

### Collect evidence from a command

```bash
trustforge evidence command \
  --key tests.passed \
  --observed-at "2026-09-11T14:30:00Z" \
  -- python -m unittest discover -s tests
```

Exit code `0` becomes `true`; nonzero becomes `false`. The command adapter uses `shell=False`, has a bounded timeout, discards stdout/stderr, and does not copy raw argv into the evidence bundle. Provenance retains only the executable, argument count, argv SHA-256 fingerprint, exit code, and explicit no-output-capture flags.

### Collect pytest evidence

```bash
trustforge evidence pytest \
  --key tests.passed \
  --observed-at "2026-09-11T14:45:00Z" \
  -- tests -q
```

The dedicated pytest adapter runs `<python> -m pytest` with `shell=False`, maps exit code `0` to `true`, and emits `source.kind: pytest`. Raw pytest arguments and test output are not copied into the evidence bundle; provenance keeps only the selected Python executable, argument count, argv SHA-256 fingerprint, exit code, and no-output-capture flags. Pytest remains an external workflow dependency and is not installed by TrustForge itself.

### Collect GitHub Actions evidence

Inside GitHub Actions:

```yaml
- name: Emit CI evidence
  if: always()
  run: |
    trustforge evidence github-actions \
      --key ci.passed \
      --conclusion "${{ job.status }}" \
      > ci-evidence.json
```

The adapter requires `GITHUB_ACTIONS=true`, maps `success` to `true` and other supported conclusions to `false`, and records non-secret runtime metadata such as repository, workflow, job, run ID/attempt, SHA, ref, event, and run URL. It does not read `GITHUB_TOKEN`, call the GitHub API, or claim that the metadata is cryptographically attested.

### Collect evidence from a JSON artifact

```bash
trustforge evidence json-artifact \
  --key tests.coverage \
  --input coverage.json \
  --value-path totals.percent \
  --observed-at "2026-09-11T14:30:00Z"
```

This extracts one JSON value and records artifact path, selected field path, SHA-256, and byte size as provenance. Numeric dotted-path components can index arrays.

### Verify whether an agent can claim completion

```bash
trustforge verify \
  examples/commitmentguard/release-contract.json \
  --evidence examples/commitmentguard/release-evidence.json \
  --as-of "2026-09-11T14:01:00Z"
```

CommitmentGuard v0.7 distinguishes full completion from partial completion, preserves evidence provenance, can reject stale or future-dated evidence, and can restrict which source kinds are allowed to prove a commitment.

### Package and verify a failure

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

### Export or replay inside a container boundary

```bash
trustforge reprocapsule export-container \
  --capsule .artifacts/reprocapsule \
  --output .artifacts/reprocapsule-container
```

```bash
trustforge reprocapsule replay-container \
  --capsule .artifacts/reprocapsule \
  --execute \
  --fail-on-divergence
```

Without `--execute`, container replay is an integrity-only preflight and does not invoke Docker.

### Gate trace redaction

```bash
trustforge reprocapsule benchmark-redaction \
  --dataset evals/reprocapsule/redaction-benchmark.jsonl \
  --min-secret-recall 1.0 \
  --min-clean-specificity 1.0
```

The bundled v0.6.0 redaction fixture is gated at 1.0/1.0. That is a regression baseline for the fixture, not a claim that arbitrary secrets are always detectable.

## CommitmentGuard v0.7 development

The active development line focuses on making agent completion claims explicit and machine-checkable.

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

New v0.7 capabilities currently include:

- contract, evidence, and report schemas v0.2;
- per-observation provenance;
- required vs optional commitments;
- structured waivers with expiry;
- deterministic `--as-of` evaluation;
- evidence `max_age_seconds` freshness policy;
- `allowed_source_kinds` trust policy;
- explicit `partial` completion state and `--accept-partial` orchestration policy;
- fail-closed handling for stale, future-dated, missing, or disallowed evidence;
- generic command exit-code evidence collection;
- dedicated pytest evidence collection with normalized `source.kind: pytest`;
- GitHub Actions runtime evidence collection with normalized `source.kind: github-actions` and no API token requirement;
- JSON artifact field evidence collection with SHA-256 provenance;
- evidence-bundle merge helper with duplicate-key rejection;
- command and pytest provenance that deliberately omit raw argv/stdout/stderr;
- adversarial regression fixtures for stale and self-claimed evidence;
- backward compatibility with legacy nested evidence documents.

Provenance is metadata, not cryptographic attestation. A hash can establish which artifact was read, but not whether its producer was trustworthy. Likewise, command/pytest exit codes and GitHub Actions runtime metadata are evidence about observed workflow state, not proof that the selected checks were sufficient or that GitHub signed the evidence.

See [`skills/commitment-guard/SKILL.md`](skills/commitment-guard/SKILL.md) and [`ROADMAP.md`](ROADMAP.md).

## ReproCapsule v0.6.0

ReproCapsule packages failure context, verifies integrity, supports host replay, exports Docker/devcontainer contexts, and can replay inside a conservatively restricted Docker runtime.

Important boundary: neither host replay nor Docker replay is claimed to be a complete security sandbox. Docker daemon access remains privileged infrastructure, and hostile workloads may require stronger isolation.

Release notes: [`docs/releases/v0.6.0.md`](docs/releases/v0.6.0.md)

## FreshPlan v0.5.0

FreshPlan focuses on long-running plans that depend on time-sensitive evidence. It supports provenance/freshness metadata, TTL/validity windows, named policies, selective invalidation, value-free refresh requests, trusted refresh adapters, replacement semantics, minimal plan patches, and deterministic large-graph regression tests.

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
- Evidence provenance does not prove that its claimed source is authentic.
- Artifact hashes do not prove the artifact producer was trustworthy.
- Command or pytest exit-code evidence does not prove the selected checks tested the right requirement.
- GitHub Actions environment metadata is useful provenance but is not a signed attestation from GitHub.
- Redaction reduces disclosure but does not prove arbitrary secrets can never appear.
- ReproCapsule host/container replay is not a complete security sandbox.
- Container export does not capture arbitrary OS/native dependency locks.

The goal is useful infrastructure with measurable boundaries, not perfect detection or novelty marketing.

## Build in public

TrustForge is still pre-1.0 and is being developed in the open. The repository includes implementation, eval fixtures, known limitations, release checklists, benchmark gates, and design tradeoffs as they evolve.

The latest stable release is **v0.6.0**. The active development milestone is **CommitmentGuard v0.7**.

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

- Development package version on `main` after this milestone merges: **0.7.0.dev3**
- Latest stable release: **v0.6.0**
- Floating stable GitHub Action ref: **`v0`**, pinned to the v0.6.0 release commit until the next verified release
- License: Apache-2.0

## Contributing

Issues, concrete failure cases, benchmark ideas, adapters, and focused PRs are welcome.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
