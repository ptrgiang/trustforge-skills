import unittest
from pathlib import Path

from trustforge.ast_detectors import compare_python_ast, scan_python_tree
from trustforge.skilldiff_v03 import compare, to_sarif


ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "evals" / "skilldiff" / "python-ast-alias" / "before"
AFTER = ROOT / "evals" / "skilldiff" / "python-ast-alias" / "after"


class PythonAstDetectorTests(unittest.TestCase):
    def test_string_literal_does_not_create_ast_subprocess_finding(self):
        result = scan_python_tree(BEFORE)
        capabilities = {finding.capability for finding in result.findings}
        self.assertNotIn("subprocess", capabilities)

    def test_aliases_and_open_mode_are_resolved(self):
        result = compare_python_ast(BEFORE, AFTER)
        capabilities = set(result["new_capabilities"])

        self.assertIn("network", capabilities)
        self.assertIn("subprocess", capabilities)
        self.assertIn("environment_read", capabilities)
        self.assertIn("credential_material", capabilities)
        self.assertIn("filesystem_write", capabilities)

        symbols = {item["symbol"] for item in result["added_findings"]}
        self.assertIn("requests.post", symbols)
        self.assertIn("subprocess.run", symbols)
        self.assertIn("os.getenv", symbols)
        self.assertIn("env:DEPLOY_TOKEN", symbols)
        self.assertIn("open(mode=w)", symbols)


class SkillDiffV03Tests(unittest.TestCase):
    def test_ast_findings_enrich_main_report(self):
        report = compare(BEFORE, AFTER)

        self.assertEqual(report["schema_version"], "0.3")
        self.assertIn("python-ast-v1", report["detectors"])
        self.assertIn("subprocess", report["ast_analysis"]["new_capabilities"])
        self.assertIn("network", report["capabilities"]["added"])
        self.assertIn("filesystem_write", report["capabilities"]["added"])

    def test_sarif_contains_python_ast_rule(self):
        report = compare(BEFORE, AFTER)
        sarif = to_sarif(report)
        rule_ids = {result.get("ruleId") for result in sarif["runs"][0]["results"]}

        self.assertIn("trustforge.python-ast.network", rule_ids)
        self.assertIn("trustforge.python-ast.subprocess", rule_ids)


if __name__ == "__main__":
    unittest.main()
