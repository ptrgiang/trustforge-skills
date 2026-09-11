# CommitmentGuard signed evidence attestations

Status: development (`0.8.0.dev1`)

CommitmentGuard v0.8 adds optional Ed25519 attestations to evidence observations. The goal is to let a completion contract require evidence whose value and provenance were signed by an explicitly trusted issuer/key pair.

## Trust model

An attestation signs a canonical payload containing:

- attestation schema version;
- algorithm (`Ed25519`);
- issuer;
- key ID;
- observation key;
- SHA-256 of the observation value;
- SHA-256 of observation provenance;
- issue time;
- optional expiry time.

The signature does not copy the raw observation value or provenance into a second document. It binds the signature to the exact canonical hashes used by CommitmentGuard.

## Verification policy

A contract evidence rule can require an attestation and optionally allow-list issuers/key IDs.

```json
{
  "key": "ci.passed",
  "truthy": true,
  "require_attestation": true,
  "allowed_attestation_issuers": ["release-ci"],
  "allowed_attestation_key_ids": ["2026-09"]
}
```

Trusted public keys are supplied separately through a trust registry. A contract cannot make an arbitrary key trusted merely by embedding that key in the same contract.

Invalid, missing, future-dated, expired, tampered, unknown-key, disallowed-issuer, and disallowed-key attestations fail closed to `UNKNOWN`.

## Trust registry

The v0.1 registry maps an `(issuer, key_id)` identity to an Ed25519 public-key PEM file.

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

`public_key_file` must be a relative path and must resolve inside the directory containing the registry. Absolute paths and `..` escapes fail closed.

Only public verification material belongs in the trust registry. Private signing keys must remain outside the repository and outside evidence bundles.

## CLI flow

Sign one observation in an evidence bundle. The signed bundle is written to stdout, so redirect it to a file when needed:

```bash
trustforge evidence sign \
  --input evidence.json \
  --key ci.passed \
  --private-key signer.pem \
  --issuer release-ci \
  --key-id 2026-09 \
  --issued-at 2026-09-11T16:01:00Z \
  --expires-at 2026-09-12T16:01:00Z \
  > signed-evidence.json
```

Verify only the attestation:

```bash
trustforge evidence verify-attestation \
  --input signed-evidence.json \
  --key ci.passed \
  --trust-registry trust-registry.json \
  --as-of 2026-09-11T16:30:00Z
```

Use signed evidence in the full completion gate:

```bash
trustforge verify contract.json \
  --evidence signed-evidence.json \
  --trust-registry trust-registry.json \
  --as-of 2026-09-11T16:30:00Z
```

## Security boundaries

A valid signature proves that the holder of the corresponding private key signed the canonical attestation payload. It does not prove that:

- the signer collected the observation correctly;
- the signer itself was uncompromised;
- the underlying CI runner/tool/source was trustworthy;
- the selected evidence was sufficient for the real-world requirement;
- a timestamp originated from a trusted time authority;
- a public-key registry was distributed securely;
- a private key was stored, rotated, or revoked correctly.

TrustForge therefore treats signatures as one stronger evidence primitive, not as a complete identity/PKI system.

## Key-management scope

The current v0.8 development line intentionally does not provide cloud KMS/HSM integration, certificate chains, transparency logs, remote signing, or automated revocation distribution. Those are future integration layers rather than requirements for the first portable attestation contract.

For production use, keep signing keys in a dedicated secret/KMS system, distribute trust registries through a controlled channel, use short-lived attestations where appropriate, rotate key IDs explicitly, and pin release commits for security-sensitive workflows.

## Regression fixture

`evals/commitmentguard/signed-attestation/` contains a synthetic public key, trust registry, contract, and signed evidence fixture. The private key used to create the fixture is not stored in the repository.

Tests cover valid signed evidence plus tampered values, expiry, issuer-policy mismatch, and trust-registry path escapes. These tests are regression evidence, not a cryptographic audit or compliance certification.
