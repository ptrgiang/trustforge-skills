from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from trustforge.commitment_evidence import (
    CommitmentEvidenceError,
    collect_command_exit,
    collect_json_artifact,
    merge_bundles,
)


class CommitmentEvidenceTests(unittest.TestCase):
    def test_command_adapter_records_exit_only_without_raw_command_data(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0)

        bundle = collect_command_exit(
            "tests.passed",
            ["python", "--api-key=super-secret", "-m", "unittest"],
            observed_at="2026-09-11T14:30:00Z",
            runner=runner,
        )

        observation = bundle["observations"]["tests.passed"]
        source = observation["source"]
        serialized = json.dumps(bundle)
        self.assertTrue(observation["value"])
        self.assertEqual(source["kind"], "command")
        self.assertEqual(source["exit_code"], 0)
        self.assertEqual(source["executable"], "python")
        self.assertEqual(source["argument_count"], 3)
        self.assertEqual(len(source["argv_sha256"]), 64)
        self.assertFalse(source["stdout_captured"])
        self.assertFalse(source["stderr_captured"])
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("--api-key", serialized)
        self.assertNotIn("argv\"", serialized)
        self.assertFalse(calls[0][1]["shell"])
        self.assertEqual(calls[0][1]["stdout"], subprocess.DEVNULL)
        self.assertEqual(calls[0][1]["stderr"], subprocess.DEVNULL)

    def test_command_adapter_false_on_nonzero_exit(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 2)

        bundle = collect_command_exit("tests.passed", ["false"], runner=runner)
        self.assertFalse(bundle["observations"]["tests.passed"]["value"])
        self.assertEqual(bundle["observations"]["tests.passed"]["source"]["exit_code"], 2)

    def test_command_adapter_rejects_unsafe_timeout(self):
        with self.assertRaises(CommitmentEvidenceError):
            collect_command_exit("tests.passed", ["echo", "ok"], timeout_seconds=0)
        with self.assertRaises(CommitmentEvidenceError):
            collect_command_exit("tests.passed", ["echo", "ok"], timeout_seconds=301)

    def test_json_artifact_adapter_extracts_value_and_hashes_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text('{"totals": {"percent": 94.5}}\n', encoding="utf-8")

            bundle = collect_json_artifact(
                "tests.coverage",
                path,
                "totals.percent",
                observed_at="2026-09-11T14:30:00Z",
            )

            observation = bundle["observations"]["tests.coverage"]
            self.assertEqual(observation["value"], 94.5)
            self.assertEqual(observation["source"]["kind"], "artifact")
            self.assertEqual(observation["source"]["value_path"], "totals.percent")
            self.assertEqual(len(observation["source"]["sha256"]), 64)
            self.assertGreater(observation["source"]["size_bytes"], 0)

    def test_json_artifact_adapter_supports_array_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text('{"checks": [{"passed": true}]}', encoding="utf-8")
            bundle = collect_json_artifact("check.passed", path, "checks.0.passed")
            self.assertTrue(bundle["observations"]["check.passed"]["value"])

    def test_json_artifact_missing_path_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            with self.assertRaises(CommitmentEvidenceError):
                collect_json_artifact("missing", path, "nested.value")

    def test_merge_bundles_rejects_duplicate_observations(self):
        left = {"schema_version": "0.2", "observations": {"a": {"value": 1}}}
        right = {"schema_version": "0.2", "observations": {"a": {"value": 2}}}
        with self.assertRaises(CommitmentEvidenceError):
            merge_bundles(left, right)

    def test_merge_bundles_combines_distinct_observations(self):
        left = {"schema_version": "0.2", "observations": {"a": {"value": 1}}}
        right = {"schema_version": "0.2", "observations": {"b": {"value": 2}}}
        merged = merge_bundles(left, right)
        self.assertEqual(set(merged["observations"]), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
