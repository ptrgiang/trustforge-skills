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

Status: v0.7 development

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
        "allowed_source_kinds": ["ci", "command"]
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

The observation value is `true` for exit code `0` and `false` otherwise. The adapter uses `shell=False`, discards stdout/stderr, and does not store raw command arguments. Provenance contains only:

- `kind: command`;
- executable;
- argument count;
- SHA-256 fingerprint of the argv sequence;
- exit code;
- explicit flags showing stdout/stderr were not captured.

This reduces the chance that credentials passed on a command line are copied into an evidence bundle. It does not make putting secrets on a command line safe.

### JSON artifact evidence

```bash
trustforge evidence json-artifact \
  --key tests.coverage \
  --input coverage.json \
  --value-path totals.percent \
  --observed-at "2026-09-11T14:30:00Z"
```

The adapter extracts one value using a dotted path and records artifact provenance including path, selected value path, SHA-256, and size. Numeric path components can index arrays.

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

CommitmentGuard v0.7 keeps the original nested evidence format valid. The new collection adapters emit schema v0.2 bundles and do not change the legacy verification path.

## Boundaries

CommitmentGuard cannot guarantee correctness when:

- the contract omitted an important user requirement;
- evidence is fabricated or comes from an untrusted source that is incorrectly allow-listed;
- provenance identifies a source but does not cryptographically prove it;
- timestamps are trustworthy in format but not in origin;
- an artifact is trustworthy by hash but its producer was compromised;
- command exit code is only a proxy for the actual requirement;
- an optional commitment was incorrectly classified as non-blocking;
- a natural-language requirement has not been compiled into a reliable check.

## v0.7 research backlog

- evidence signatures / attestations;
- natural-language commitment extraction;
- dedicated pytest and GitHub Actions adapters;
- package manifest, API diff, and browser-task adapters;
- temporal commitments and deadlines beyond observation freshness;
- hierarchical commitments for multi-agent workflows;
- policy preventing completion language until verification passes.
