import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trustforge.commitment_attestation import sign_observation
from trustforge.commitment_guard import CommitmentGuardError, verify


class CommitmentAttestationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.provenance = {
            "source": {"kind": "github-actions", "run_id": "123"},
            "observed_at": "2026-09-11T14:00:00Z",
        }
        self.attestation = sign_observation(
            observation_key="ci.passed",
            value=True,
            provenance=self.provenance,
            private_key=self.private_key,
            issuer="ci.example",
            key_id="release-key",
            issued_at="2026-09-11T14:00:10Z",
            expires_at="2026-09-11T15:00:10Z",
        )
        self.contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "ci-pass",
                    "description": "CI passes with trusted signed evidence",
                    "evidence": {
                        "key": "ci.passed",
                        "truthy": True,
                        "allowed_source_kinds": ["github-actions"],
                        "require_attestation": True,
                        "allowed_attestation_issuers": ["ci.example"],
                        "allowed_attestation_key_ids": ["release-key"],
                    },
                }
            ],
        }

    def _evidence(self, *, include_attestation: bool = True):
        item = {"value": True, **self.provenance}
        if include_attestation:
            item["attestation"] = self.attestation
        return {"schema_version": "0.2", "observations": {"ci.passed": item}}

    def test_verified_attestation_allows_completion(self):
        report = verify(
            self.contract,
            self._evidence(),
            as_of="2026-09-11T14:30:00Z",
            trusted_attestation_keys={("ci.example", "release-key"): self.public_key},
        )
        self.assertEqual(report["completion_state"], "verified_complete")
        result = report["commitments"][0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["attestation"]["issuer"], "ci.example")
        self.assertNotIn("signature", result["attestation"])

    def test_missing_attestation_fails_closed(self):
        report = verify(
            self.contract,
            self._evidence(include_attestation=False),
            as_of="2026-09-11T14:30:00Z",
            trusted_attestation_keys={("ci.example", "release-key"): self.public_key},
        )
        self.assertEqual(report["completion_state"], "not_verified")
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")
        self.assertIn("attestation required", report["commitments"][0]["detail"])

    def test_missing_trust_store_fails_closed(self):
        report = verify(self.contract, self._evidence(), as_of="2026-09-11T14:30:00Z")
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")
        self.assertIn("trusted attestation keys required", report["commitments"][0]["detail"])

    def test_wrong_trusted_key_fails_closed(self):
        other_key = Ed25519PrivateKey.generate().public_key()
        report = verify(
            self.contract,
            self._evidence(),
            as_of="2026-09-11T14:30:00Z",
            trusted_attestation_keys={("ci.example", "release-key"): other_key},
        )
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")
        self.assertIn("invalid attestation signature", report["commitments"][0]["detail"])

    def test_issuer_allowlist_fails_closed(self):
        contract = {**self.contract, "commitments": [{**self.contract["commitments"][0]}]}
        contract["commitments"][0]["evidence"] = {
            **self.contract["commitments"][0]["evidence"],
            "allowed_attestation_issuers": ["prod.example"],
        }
        report = verify(
            contract,
            self._evidence(),
            as_of="2026-09-11T14:30:00Z",
            trusted_attestation_keys={("ci.example", "release-key"): self.public_key},
        )
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")
        self.assertIn("issuer", report["commitments"][0]["detail"])

    def test_attestation_allowlist_requires_attestation_policy(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "bad",
                    "description": "bad policy",
                    "evidence": {
                        "key": "ci.passed",
                        "truthy": True,
                        "allowed_attestation_issuers": ["ci.example"],
                    },
                }
            ],
        }
        with self.assertRaisesRegex(CommitmentGuardError, "require_attestation must be true"):
            verify(contract, self._evidence(), as_of="2026-09-11T14:30:00Z")


if __name__ == "__main__":
    unittest.main()
