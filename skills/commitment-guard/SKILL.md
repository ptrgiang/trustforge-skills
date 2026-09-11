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
- `UNKNOWN` — required evidence is missing or cannot be evaluated;
- `WAIVED` — an explicit waiver is recorded in the contract.

v0.7 also distinguishes required and optional commitments so the overall result can be:

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
        "truthy": true
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
        "kind": "command",
        "ref": "python -m unittest discover -s tests -v"
      }
    }
  }
}
```

The verifier preserves this provenance in the commitment result. Legacy nested evidence remains supported.

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
    "ticket": "INC-42"
  }
}
```

Supported waiver metadata is `reason`, `approved_by`, `ticket`, and `expires_at`. A reason is mandatory. Legacy string waivers remain accepted for compatibility.

An agent must not invent a waiver to make a completion claim pass.

## CLI

Strict completion gate:

```bash
trustforge verify ./contract.json --evidence ./evidence.json
```

Machine-readable output:

```bash
trustforge verify ./contract.json --evidence ./evidence.json --json
```

Allow a `partial` result to exit successfully when all required commitments are satisfied:

```bash
trustforge verify ./contract.json \
  --evidence ./evidence.json \
  --accept-partial
```

Exit codes:

- `0`: verified complete, or `partial` when `--accept-partial` is explicitly supplied;
- `3`: invalid contract/evidence, required blocker, or strict completion gate not satisfied.

## Procedure

1. Extract explicit user commitments before or during execution.
2. Give each commitment a stable ID.
3. Mark acceptance-critical commitments as required.
4. Define machine-checkable evidence for each commitment.
5. Gather evidence from tools rather than agent self-assessment where possible.
6. Attach provenance to observations when available.
7. Verify the contract.
8. Do not claim full completion for `partial` or `not_verified`.
9. Record waivers only when they reflect an explicit authorized decision.

## Compatibility

CommitmentGuard v0.7 keeps the original contract/evidence examples valid:

```json
{
  "commitments": [
    {
      "id": "C1",
      "description": "Coverage remains at least 90%",
      "evidence": {"key": "tests.coverage", "gte": 90}
    }
  ]
}
```

with evidence:

```json
{"tests": {"coverage": 92.4}}
```

## Boundaries

CommitmentGuard cannot guarantee correctness when:

- the contract omitted an important user requirement;
- evidence is fabricated or comes from an untrusted source;
- provenance identifies a source but does not cryptographically prove it;
- the evidence key measures a proxy rather than the actual requirement;
- an optional commitment was incorrectly classified as non-blocking;
- a natural-language requirement has not been compiled into a reliable check.

## v0.7 research backlog

- evidence signatures / attestations;
- natural-language commitment extraction;
- direct adapters for pytest, GitHub Actions, package manifests, API diffs, and browser tasks;
- temporal commitments and deadlines;
- hierarchical commitments for multi-agent workflows;
- policy preventing completion language until verification passes.
