from __future__ import annotations

import unittest

from trustforge.commitment_guard import CommitmentGuardError, verify


class CommitmentGuardV07Tests(unittest.TestCase):
    def test_provenance_is_preserved_for_observation_bundle(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "C1",
                    "description": "Tests pass",
                    "evidence": {"key": "tests.passed", "truthy": True},
                }
            ],
        }
        evidence = {
            "schema_version": "0.2",
            "observations": {
                "tests.passed": {
                    "value": True,
                    "observed_at": "2026-09-11T14:00:00Z",
                    "source": {"kind": "command", "ref": "pytest -q"},
                }
            },
        }

        report = verify(contract, evidence)

        self.assertEqual(report["completion_state"], "verified_complete")
        self.assertTrue(report["verified_complete"])
        self.assertEqual(report["commitments"][0]["provenance"]["source"]["kind"], "command")
        self.assertEqual(report["commitments"][0]["provenance"]["observed_at"], "2026-09-11T14:00:00Z")

    def test_optional_failure_produces_partial_without_required_blocker(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "C1",
                    "description": "Required tests pass",
                    "evidence": {"key": "tests.passed", "truthy": True},
                },
                {
                    "id": "C2",
                    "description": "Optional coverage target",
                    "required": False,
                    "evidence": {"key": "tests.coverage", "gte": 95},
                },
            ],
        }
        evidence = {
            "schema_version": "0.2",
            "observations": {
                "tests.passed": {"value": True},
                "tests.coverage": {"value": 91.2},
            },
        }

        report = verify(contract, evidence)

        self.assertEqual(report["completion_state"], "partial")
        self.assertFalse(report["verified_complete"])
        self.assertTrue(report["required_satisfied"])
        self.assertEqual(report["summary"]["required_blockers"], 0)

    def test_required_failure_is_not_verified(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "C1",
                    "description": "No dependency additions",
                    "evidence": {"key": "dependencies.added", "equals": []},
                }
            ],
        }
        evidence = {
            "schema_version": "0.2",
            "observations": {"dependencies.added": {"value": ["requests"]}},
        }

        report = verify(contract, evidence)

        self.assertEqual(report["completion_state"], "not_verified")
        self.assertFalse(report["required_satisfied"])
        self.assertEqual(report["summary"]["required_blockers"], 1)

    def test_structured_waiver_is_reported(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {
                    "id": "C1",
                    "description": "Coverage is 95%",
                    "waiver": {
                        "reason": "Accepted for hotfix",
                        "approved_by": "release-owner",
                        "ticket": "INC-42",
                    },
                }
            ],
        }

        report = verify(contract, {})

        self.assertEqual(report["completion_state"], "verified_complete")
        self.assertEqual(report["commitments"][0]["waiver"]["ticket"], "INC-42")

    def test_duplicate_commitment_ids_fail_closed(self):
        contract = {
            "schema_version": "0.2",
            "commitments": [
                {"id": "C1", "description": "a", "evidence": {"key": "a", "truthy": True}},
                {"id": "C1", "description": "b", "evidence": {"key": "b", "truthy": True}},
            ],
        }
        with self.assertRaises(CommitmentGuardError):
            verify(contract, {})

    def test_legacy_nested_evidence_remains_compatible(self):
        contract = {
            "commitments": [
                {
                    "id": "C1",
                    "description": "Coverage remains at least 90%",
                    "evidence": {"key": "tests.coverage", "gte": 90},
                }
            ]
        }
        report = verify(contract, {"tests": {"coverage": 92}})
        self.assertTrue(report["verified_complete"])
        self.assertEqual(report["completion_state"], "verified_complete")


if __name__ == "__main__":
    unittest.main()
