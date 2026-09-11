---
name: commitment-guard
description: Prevent an AI agent from claiming a task is complete until explicit user commitments are matched with machine-checkable evidence or an explicit waiver.
license: Apache-2.0
metadata:
  trustforge:
    maturity: experimental
    category: completion-verification
    destructive: false
---

# CommitmentGuard

Status: v0.7.0 release candidate

CommitmentGuard verifies whether an agent has enough evidence to make a completion claim.

## Core rule

**A confident completion statement is not evidence.**

Every commitment resolves to one of:

- `PASS` — evidence exists and satisfies the rule;
- `FAIL` — evidence contradicts the rule;
- `UNKNOWN` — required evidence is missing, stale, untrusted, future-dated, or cannot be evaluated;
- `WAIVED` — an explicit, still-valid waiver is recorded in the contract.

v0.7 distinguishes required and optional commitments so the overall result can be:

- `verified_complete` — every commitment is `PASS` or `WAIVED`;
- `partial` — all required commitments are satisfied, but one or more optional commitments are `FAIL` or `UNKNOWN`;
- `not_verified` — at least one required commitment is `FAIL` or `UNKNOWN`.

## Contract v0.2

```json
{
  "schema_version": "0.2",
  "commitments": [
    {
      "id": "tests-pass",
      "description": "The test suite passes",
      "evidence": {
        "key": "tests.passed",
        "truthy": true,
        "max_age_seconds": 300,
        "allowed_source_kinds": ["ci", "command", "pytest", "github-actions"]
      }
    },
    {
      "id": "coverage-target",
      "description": "Coverage is at least 95%",
      "required": false,
      "evidence": {
        "key": "tests.coverage",
        "gte": 95
      }
    }
  ]
}
```

`required` defaults to `true` for backward compatibility.

## Evidence bundle v0.2

Evidence can carry provenance instead of being only a nested value map:

```json
{
  "schema_version": "0.2",
  "observations": {
    "tests.passed": {
      "value": true,
      "observed_at": "2026-09-11T14:00:00Z",
      "source": {
        "kind": "ci",
        "ref": "run-123"
      }
    }
  }
}
```

The verifier preserves this provenance in the commitment result. Legacy nested evidence remains supported.

## Evidence policies

A commitment can constrain the evidence used to prove it:

- `max_age_seconds` requires `observed_at` and rejects stale or future-dated observations;
- `allowed_source_kinds` requires `source.kind` and rejects sources outside the allow-list.

If evidence violates either policy, CommitmentGuard returns `UNKNOWN` rather than evaluating the value as proof.

## Evidence collection adapters

v0.7 can produce evidence bundles directly from developer workflows.

### Command exit evidence

```bash
trustforge evidence command \
  --key tests.passed \
  --observed-at "2026-09-11T14:30:00Z" \
  -- python -m unittest discover -s tests
```

The observation value is `true` for exit code `0` and `false` otherwise. The adapter uses `shell=False`, discards stdout/stderr, and does not store raw command arguments. Provenance contains only executable, argument count, argv SHA-256, exit code, and explicit no-output-capture flags.

This reduces the chance that credentials passed on a command line are copied into an evidence bundle. It does not make putting secrets on a command line safe.

### Pytest evidence

```bash
trustforge evidence pytest \
  --key tests.passed \
  --observed-at "2026-09-11T14:45:00Z" \
  -- tests -q
```

The adapter runs `<python> -m pytest` and emits `source.kind: pytest`. Exit code `0` becomes `true`; any nonzero exit becomes `false`. It uses the same bounded `shell=False` runner as command evidence and deliberately does not copy raw pytest arguments, stdout, or stderr into the bundle.

Pytest is not installed by TrustForge. The adapter uses the pytest installation available in the selected Python environment.

### GitHub Actions evidence

Inside a workflow:

```yaml
- name: Emit CI evidence
  if: always()
  run: |
    trustforge evidence github-actions \
      --key ci.passed \
      --conclusion "${{ job.status }}" \
      > ci-evidence.json
```

The adapter requires `GITHUB_ACTIONS=true`. It maps `success` to `true`; `failure`, `cancelled`, and `skipped` map to `false`. Provenance is assembled from a whitelist of non-secret runtime metadata including repository, workflow/job, run ID/attempt, commit SHA, run URL, and optional ref/event name.

It does not read `GITHUB_TOKEN` and does not call the GitHub API. Runtime environment metadata is useful provenance but is not a signed attestation from GitHub.

### JSON artifact evidence

```bash
trustforge evidence json-artifact \
  --key tests.coverage \
  --input coverage.json \
  --value-path totals.percent \
  --observed-at "2026-09-11T14:30:00Z"
```

The adapter extracts one value using a dotted path and records artifact provenance including path, selected value path, SHA-256, and size. Numeric path components can index arrays.

### Package-manifest evidence

```bash
trustforge evidence package-manifest \
  --key dependencies.manifest_sha256 \
  --input pyproject.toml
```

The observation value is the exact SHA-256 digest of the manifest bytes. Provenance records:

- `kind: package-manifest`;
- path;
- detected manifest type;
- SHA-256;
- byte size.

The adapter recognizes common Python and Node manifest/lock filenames for descriptive provenance, but it does not parse dependency semantics or claim that the dependency set is safe. An exact hash is useful when the completion contract requires the package snapshot to match an approved baseline.

### API-diff evidence

```bash
trustforge evidence api-diff \
  --key api.no_removed_operations \
  --before openapi-before.json \
  --after openapi-after.json
```

The v0.7 API-diff contract accepts OpenAPI-like UTF-8 JSON documents with a `paths` mapping. It compares HTTP method + path operations and emits `true` when no operation was removed.

Provenance stores:

- `kind: api-diff`;
- format version `openapi-path-methods-v1`;
- before/after path, SHA-256, and size;
- before/after operation counts;
- added/removed operation counts;
- `operation_names_captured: false`.

Endpoint names are deliberately not copied into the evidence bundle. This is a narrow removal detector, not a general API compatibility engine: request/response schema changes, parameter changes, semantics, auth behavior, and non-OpenAPI contracts are outside this adapter's v0.7 scope.

Application code can also use `merge_bundles()` to combine distinct v0.2 observations. Duplicate keys fail closed.

## Supported checks

- `equals`
- `gte`
- `lte`
- `truthy`
- `contains`

A rule must contain exactly one supported operator. Evidence keys use dot notation in legacy bundles and direct observation IDs in v0.2 bundles.

## Structured waivers

v0.7 supports explicit waiver metadata:

```json
{
  "id": "coverage-target",
  "description": "Coverage is at least 95%",
  "waiver": {
    "reason": "Accepted for emergency hotfix",
    "approved_by": "release-owner",
    "ticket": "INC-42",
    "expires_at": "2026-09-12T00:00:00Z"
  }
}
```

Supported waiver metadata is `reason`, `approved_by`, `ticket`, and `expires_at`. A reason is mandatory. Expired waivers resolve to `UNKNOWN`. Legacy string waivers remain accepted for compatibility.

An agent must not invent a waiver to make a completion claim pass.

## Verification CLI

Strict completion gate:

```bash
trustforge verify ./contract.json --evidence ./evidence.json
```

Deterministic freshness/expiry evaluation:

```bash
trustforge verify ./contract.json \
  --evidence ./evidence.json \
  --as-of "2026-09-11T14:01:00Z"
```

Allow a `partial` result to exit successfully when all required commitments are satisfied:

```bash
trustforge verify ./contract.json \
  --evidence ./evidence.json \
  --accept-partial
```

Exit codes:

- `0`: successful evidence collection, verified complete, or accepted partial completion;
- `3`: CommitmentGuard verification did not satisfy the selected completion policy;
- `8`: evidence collection failed.

## Procedure

1. Extract explicit user commitments before or during execution.
2. Give each commitment a stable ID.
3. Mark acceptance-critical commitments as required.
4. Define machine-checkable evidence for each commitment.
5. Define freshness/source policy when evidence can age or comes from multiple trust domains.
6. Collect evidence from explicit tools/adapters rather than agent self-assessment where possible.
7. Preserve provenance without unnecessarily copying sensitive command output or arguments.
8. Verify the contract at an explicit evaluation time for deterministic workflows.
9. Do not claim full completion for `partial` or `not_verified`.
10. Record waivers only when they reflect an explicit authorized decision.

## Compatibility

CommitmentGuard v0.7 keeps the original nested evidence format valid. Collection adapters emit schema v0.2 bundles and do not change the legacy verification path. Contract/evidence/report schema `0.2` is the v0.7 release line.

## Boundaries

CommitmentGuard cannot guarantee correctness when:

- the contract omitted an important user requirement;
- evidence is fabricated or comes from an untrusted source that is incorrectly allow-listed;
- provenance identifies a source but does not cryptographically prove it;
- timestamps are trustworthy in format but not in origin;
- an artifact/package manifest is trustworthy by hash but its producer or dependencies were compromised;
- command or pytest exit status is only a proxy for the actual requirement;
- the selected pytest scope omits important tests;
- GitHub Actions environment metadata was altered or the explicit conclusion was supplied incorrectly;
- API compatibility breaks through schema/parameter/semantic changes without removing a path+method operation;
- an optional commitment was incorrectly classified as non-blocking;
- a natural-language requirement has not been compiled into a reliable check.

## Post-v0.7 research backlog

- signed evidence attestations;
- natural-language commitment extraction;
- browser-task evidence adapters;
- richer API compatibility analysis;
- temporal commitments and deadlines beyond observation freshness;
- hierarchical commitments for multi-agent workflows;
- policy preventing completion language until verification passes.
