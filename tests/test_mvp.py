import json
import tempfile
import unittest
from pathlib import Path

from trustforge.commitment_guard import verify
from trustforge.skilldiff import compare


class SkillDiffTests(unittest.TestCase):
    def test_detects_new_network_and_subprocess_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before"
            after = root / "after"
            before.mkdir()
            after.mkdir()
            (before / "SKILL.md").write_text("# Safe skill\nReads local text only.\n", encoding="utf-8")
            (after / "SKILL.md").write_text(
                "# Changed skill\nCall https://api.example.com and run subprocess.run(...).\n",
                encoding="utf-8",
            )

            report = compare(before, after)

            self.assertIn("network", report["capabilities"]["added"])
            self.assertIn("subprocess", report["capabilities"]["added"])
            self.assertIn("api.example.com", report["network_domains"]["added"])
            self.assertIn(report["risk"]["level"], {"medium", "high"})


class CommitmentGuardTests(unittest.TestCase):
    def test_unknown_evidence_blocks_completion(self):
        contract = {
            "commitments": [
                {
                    "id": "C1",
                    "description": "Coverage remains at least 90%",
                    "evidence": {"key": "tests.coverage", "gte": 90},
                },
                {
                    "id": "C2",
                    "description": "No dependency changes",
                    "evidence": {"key": "dependencies.added", "equals": []},
                },
            ]
        }
        evidence = {"dependencies": {"added": []}}

        report = verify(contract, evidence)

        self.assertFalse(report["verified_complete"])
        self.assertEqual(report["summary"]["unknown"], 1)
        self.assertEqual(report["summary"]["pass"], 1)

    def test_explicit_waiver_does_not_block(self):
        contract = {
            "commitments": [
                {
                    "id": "C1",
                    "description": "Coverage remains at least 90%",
                    "waiver": "User explicitly accepted 88% for this change.",
                }
            ]
        }

        report = verify(contract, {})

        self.assertTrue(report["verified_complete"])
        self.assertEqual(report["summary"]["waived"], 1)


if __name__ == "__main__":
    unittest.main()
