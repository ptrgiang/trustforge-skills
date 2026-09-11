import json
import tempfile
import unittest
from pathlib import Path

from trustforge.commitment_guard import verify
from trustforge.skilldiff import compare, to_sarif


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

    def test_trigger_scope_dependency_secret_and_manifest_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before"
            after = root / "after"
            before.mkdir()
            after.mkdir()

            (before / "SKILL.md").write_text(
                "---\nname: csv-helper\ndescription: Use when converting CSV files.\n---\n",
                encoding="utf-8",
            )
            (after / "SKILL.md").write_text(
                "---\nname: data-helper\ndescription: Use for spreadsheets, reports, analytics, finance, CSV and Excel tasks.\n---\n"
                "Call https://api.example.com and subprocess.run(...).\n",
                encoding="utf-8",
            )
            (after / "main.py").write_text(
                'import os\nTOKEN = os.getenv("API_TOKEN")\n',
                encoding="utf-8",
            )
            (after / "requirements.txt").write_text("httpx>=0.27\n", encoding="utf-8")
            (after / "trustforge.json").write_text(
                json.dumps({"capabilities": ["network"]}),
                encoding="utf-8",
            )

            report = compare(before, after)

            self.assertEqual(report["schema_version"], "0.2")
            self.assertIn(report["trigger_scope"]["estimated_expansion"], {"medium", "high"})
            self.assertIn("finance", report["trigger_scope"]["added_terms"])
            self.assertIn("httpx", report["dependencies"]["added"])
            self.assertIn("API_TOKEN", report["secret_access"]["added"])
            self.assertIn("subprocess", report["capability_manifest"]["undeclared_observed"])
            self.assertTrue(report["capabilities"]["evidence_after"]["network"][0]["line"] >= 1)

    def test_repository_adversarial_fixture(self):
        root = Path(__file__).resolve().parents[1] / "evals" / "skilldiff" / "trigger-expansion"
        report = compare(root / "before", root / "after")

        self.assertIn(report["trigger_scope"]["estimated_expansion"], {"medium", "high"})
        self.assertIn("httpx", report["dependencies"]["added"])
        self.assertIn("API_TOKEN", report["secret_access"]["added"])
        self.assertIn("subprocess", report["capability_manifest"]["undeclared_observed"])

    def test_sarif_contains_locations_for_new_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before"
            after = root / "after"
            before.mkdir()
            after.mkdir()
            (before / "SKILL.md").write_text("Use when reading local files.\n", encoding="utf-8")
            (after / "SKILL.md").write_text(
                "Use when reading local files.\nCall https://api.example.com.\n",
                encoding="utf-8",
            )

            sarif = to_sarif(compare(before, after))
            results = sarif["runs"][0]["results"]

            self.assertTrue(any(item["ruleId"] == "trustforge.capability.network" for item in results))
            located = next(item for item in results if item["ruleId"] == "trustforge.capability.network")
            self.assertEqual(
                located["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                "SKILL.md",
            )


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
