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

Status: v0.8.0

CommitmentGuard verifies whether an agent has enough evidence to make a completion claim.

## Core rule

**A confident completion statement is not evidence.**

Every commitment resolves to one of:

- `PASS` — evidence exists and satisfies the rule;
- `FAIL` — evidence contradicts the rule;
- `UNKNOWN` — required evidence is missing, stale, untrusted, future-dated, unsigned when signing is required, or cannot be evaluated;
- `WAIVED` — an explicit, still-valid waiver is recorded in the contract.

Overall completion states remain:

- `verified_complete` — every commitment is `PASS` or `WAIVED`;
- `partial` — all required commitments are satisfied, but one or more optional commitments are incomplete;
- `not_verified` — at least one required commitment is `FAIL` or `UNKNOWN`.

## Contract and evidence compatibility

CommitmentGuard v0.8 keeps the v0.7 contract/evidence/report schema line (`0.2`) and legacy nested-evidence compatibility. Signed attestations are optional unless a contract explicitly requires them.

A normal evidence rule may still use one of:

- `equals`
- `gte`
- `lte`
- `truthy`
- `contains`

plus policies such as:

- `max_age_seconds`
- `allowed_source_kinds`

## Signed evidence attestations

v0.8 adds an optional Ed25519 trust layer. An attestation binds a signature to:

- observation key;
- SHA-256 of the canonical observation value;
- SHA-256 of canonical provenance metadata;
- issuer;
- key ID;
- issue time;
- optional expiry.

Example policy:

```json
{
  "key": "ci.passed",
  "truthy": true,
  "require_attestation": true,
  "allowed_attestation_issuers": ["release-ci"],
  "allowed_attestation_key_ids": ["2026-09"]
}
```

If `require_attestation` is enabled, missing, malformed, invalid-signature, tampered, future-dated, expired, unknown-key, disallowed-issuer, or disallowed-key attestations resolve to `UNKNOWN`.

## Trust registry

Trusted verification keys are supplied separately from the completion contract:

```json
{
  "schema_version": "0.1",
  "keys": [
    {
      "issuer": "release-ci",
      "key_id": "2026-09",
      "public_key_file": "release-ci-2026-09.pub.pem"
    }
  ]
}
```

`public_key_file` must be relative and must resolve inside the trust-registry directory. Absolute paths and parent-directory escapes fail closed.

Only public verification material belongs in the registry. Private signing keys must remain outside repositories, evidence bundles, and verification reports.

## Attestation CLI

Sign one observation:

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

Verify only the attestation:

```bash
trustforge evidence verify-attestation \
  --input signed-evidence.json \
  --key ci.passed \
  --trust-registry trust-registry.json \
  --as-of 2026-09-12T01:00:00Z
```

Use signed evidence in the full completion gate:

```bash
trustforge verify contract.json \
  --evidence signed-evidence.json \
  --trust-registry trust-registry.json \
  --as-of 2026-09-12T01:00:00Z
```

## Evidence collection adapters

The v0.7 adapters remain available:

- `trustforge evidence command`
- `trustforge evidence pytest`
- `trustforge evidence github-actions`
- `trustforge evidence json-artifact`
- `trustforge evidence package-manifest`
- `trustforge evidence api-diff`

Their provenance can now be cryptographically bound by a v0.8 attestation, but a valid signature does not make a weak or incomplete underlying check sufficient.

## Structured waivers

Structured waivers still support:

- `reason` — required;
- `approved_by`;
- `ticket`;
- `expires_at`.

Expired waivers resolve to `UNKNOWN`. Agents must not invent waivers.

## Procedure

1. Extract explicit user commitments before or during execution.
2. Give each commitment a stable ID.
3. Mark acceptance-critical commitments as required.
4. Define machine-checkable evidence for each commitment.
5. Define freshness/source policy where needed.
6. Require signed attestations only where signer authenticity materially improves the trust decision.
7. Keep trusted public keys outside the completion contract.
8. Keep private signing keys outside repositories and evidence bundles.
9. Collect evidence from explicit tools/adapters rather than agent self-assessment where possible.
10. Verify at an explicit `--as-of` time for deterministic workflows.
11. Do not claim full completion for `partial` or `not_verified`.
12. Record waivers only when they reflect an explicit authorized decision.

## Security boundaries

A valid Ed25519 signature proves that the holder of the corresponding private key signed the canonical payload. It does **not** prove that:

- the signer collected the observation correctly;
- the signer or CI runner was uncompromised;
- the selected evidence was sufficient for the real-world requirement;
- timestamps came from a trusted time authority;
- the trust registry was distributed securely;
- a private key was stored, rotated, or revoked correctly.

v0.8 is therefore a signed-evidence primitive, not a complete identity or PKI system.

The release intentionally does not provide cloud KMS/HSM integration, remote signing, certificate chains, transparency logs, or automatic revocation distribution.

## Regression evidence

`evals/commitmentguard/signed-attestation/` contains synthetic public verification material, a trust registry, contract, and signed evidence fixture. The private key used to create the fixture is not committed.

Regression tests cover valid signatures, tampered observations, expiry, issuer mismatch, unknown keys, and trust-registry path escapes. These tests are regression evidence, not a cryptographic audit or compliance certification.

## Post-v0.8 research backlog

- cloud KMS/HSM and remote-signing adapters;
- key revocation/distribution and transparency mechanisms;
- natural-language commitment extraction;
- browser-task evidence adapters;
- richer API compatibility analysis;
- temporal commitments and deadlines beyond evidence freshness;
- hierarchical commitments for multi-agent workflows;
- completion-language policy integration.
