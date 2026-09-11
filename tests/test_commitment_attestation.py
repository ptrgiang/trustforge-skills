import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trustforge.commitment_attestation import (
    AttestationError,
    sign_observation,
    verify_observation_attestation,
)


class CommitmentAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.trusted = {("ci.example", "release-key"): self.public_key}
        self.value = True
        self.provenance = {
            "source": {"kind": "github-actions", "run_id": "123"},
            "observed_at": "2026-09-11T14:00:00Z",
        }

    def _attestation(self):
        return sign_observation(
            observation_key="ci.passed",
            value=self.value,
            provenance=self.provenance,
            private_key=self.private_key,
            issuer="ci.example",
            key_id="release-key",
            issued_at="2026-09-11T14:00:10Z",
            expires_at="2026-09-11T15:00:10Z",
        )

    def test_sign_and_verify(self):
        result = verify_observation_attestation(
            observation_key="ci.passed",
            value=self.value,
            provenance=self.provenance,
            attestation=self._attestation(),
            trusted_keys=self.trusted,
            as_of="2026-09-11T14:30:00Z",
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["issuer"], "ci.example")
        self.assertEqual(result["key_id"], "release-key")

    def test_tampered_value_fails(self):
        with self.assertRaisesRegex(AttestationError, "does not match observation"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=False,
                provenance=self.provenance,
                attestation=self._attestation(),
                trusted_keys=self.trusted,
                as_of="2026-09-11T14:30:00Z",
            )

    def test_swapped_provenance_fails(self):
        changed = copy.deepcopy(self.provenance)
        changed["source"]["run_id"] = "999"
        with self.assertRaisesRegex(AttestationError, "does not match observation"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=self.value,
                provenance=changed,
                attestation=self._attestation(),
                trusted_keys=self.trusted,
                as_of="2026-09-11T14:30:00Z",
            )

    def test_wrong_issuer_key_is_untrusted(self):
        attestation = self._attestation()
        with self.assertRaisesRegex(AttestationError, "untrusted attestation key"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=self.value,
                provenance=self.provenance,
                attestation=attestation,
                trusted_keys={("other.example", "release-key"): self.public_key},
                as_of="2026-09-11T14:30:00Z",
            )

    def test_expired_attestation_fails(self):
        with self.assertRaisesRegex(AttestationError, "expired"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=self.value,
                provenance=self.provenance,
                attestation=self._attestation(),
                trusted_keys=self.trusted,
                as_of="2026-09-11T15:00:10Z",
            )

    def test_future_dated_attestation_fails(self):
        with self.assertRaisesRegex(AttestationError, "future-dated"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=self.value,
                provenance=self.provenance,
                attestation=self._attestation(),
                trusted_keys=self.trusted,
                as_of="2026-09-11T14:00:00Z",
            )

    def test_invalid_signature_fails(self):
        attestation = self._attestation()
        signature = attestation["signature"]
        attestation["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaisesRegex(AttestationError, "invalid attestation signature"):
            verify_observation_attestation(
                observation_key="ci.passed",
                value=self.value,
                provenance=self.provenance,
                attestation=attestation,
                trusted_keys=self.trusted,
                as_of="2026-09-11T14:30:00Z",
            )

    def test_expiry_must_follow_issue_time(self):
        with self.assertRaisesRegex(AttestationError, "expires_at must be later"):
            sign_observation(
                observation_key="ci.passed",
                value=self.value,
                provenance=self.provenance,
                private_key=self.private_key,
                issuer="ci.example",
                key_id="release-key",
                issued_at="2026-09-11T14:00:10Z",
                expires_at="2026-09-11T14:00:10Z",
            )


if __name__ == "__main__":
    unittest.main()
