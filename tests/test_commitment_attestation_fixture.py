from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from trustforge.commitment_attestation import load_trust_registry
from trustforge.commitment_guard import verify


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "commitmentguard" / "signed-attestation"


class CommitmentAttestationFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
        self.evidence = json.loads((FIXTURE / "evidence.json").read_text(encoding="utf-8"))
        self.trusted = load_trust_registry(FIXTURE / "trust-registry.json")

    def test_valid_signed_fixture_verifies_complete(self):
        report = verify(
            self.contract,
            self.evidence,
            as_of="2026-09-11T16:30:00Z",
            trusted_attestation_keys=self.trusted,
        )
        self.assertEqual(report["completion_state"], "verified_complete")
        self.assertEqual(report["commitments"][0]["status"], "PASS")
        self.assertTrue(report["commitments"][0]["attestation"]["verified"])

    def test_tampered_value_fails_closed(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["observations"]["ci.passed"]["value"] = False
        report = verify(
            self.contract,
            evidence,
            as_of="2026-09-11T16:30:00Z",
            trusted_attestation_keys=self.trusted,
        )
        self.assertEqual(report["completion_state"], "not_verified")
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")

    def test_expired_attestation_fails_closed(self):
        report = verify(
            self.contract,
            self.evidence,
            as_of="2026-09-13T00:00:00Z",
            trusted_attestation_keys=self.trusted,
        )
        self.assertEqual(report["completion_state"], "not_verified")
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")

    def test_wrong_issuer_policy_fails_closed(self):
        contract = copy.deepcopy(self.contract)
        contract["commitments"][0]["evidence"]["allowed_attestation_issuers"] = ["other-ci"]
        report = verify(
            contract,
            self.evidence,
            as_of="2026-09-11T16:30:00Z",
            trusted_attestation_keys=self.trusted,
        )
        self.assertEqual(report["completion_state"], "not_verified")
        self.assertEqual(report["commitments"][0]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
