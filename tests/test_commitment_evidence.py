from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from trustforge.commitment_evidence import (
    CommitmentEvidenceError,
    collect_api_diff,
    collect_command_exit,
    collect_github_actions,
    collect_json_artifact,
    collect_package_manifest,
    collect_pytest,
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

    def test_pytest_adapter_builds_python_m_pytest_without_raw_args(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0)

        bundle = collect_pytest(
            "tests.passed",
            ["tests/test_api.py", "-q", "--token=super-secret"],
            python_executable="python3",
            observed_at="2026-09-11T14:45:00Z",
            runner=runner,
        )

        observation = bundle["observations"]["tests.passed"]
        source = observation["source"]
        serialized = json.dumps(bundle)
        self.assertTrue(observation["value"])
        self.assertEqual(calls[0][0][:3], ["python3", "-m", "pytest"])
        self.assertFalse(calls[0][1]["shell"])
        self.assertEqual(source["kind"], "pytest")
        self.assertEqual(source["python_executable"], "python3")
        self.assertEqual(source["argument_count"], 3)
        self.assertEqual(source["exit_code"], 0)
        self.assertEqual(len(source["argv_sha256"]), 64)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("test_api.py", serialized)

    def test_pytest_adapter_nonzero_exit_is_false(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1)

        bundle = collect_pytest("tests.passed", ["tests"], runner=runner)
        self.assertFalse(bundle["observations"]["tests.passed"]["value"])
        self.assertEqual(bundle["observations"]["tests.passed"]["source"]["exit_code"], 1)

    def test_github_actions_success_uses_runtime_metadata_without_token(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "ptrgiang/trustforge-skills",
            "GITHUB_RUN_ID": "12345",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_WORKFLOW": "CI",
            "GITHUB_JOB": "test",
            "GITHUB_SHA": "abcdef123456",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_TOKEN": "must-not-appear",
        }
        bundle = collect_github_actions(
            "ci.passed",
            "success",
            observed_at="2026-09-11T14:55:00Z",
            environment=env,
        )
        observation = bundle["observations"]["ci.passed"]
        source = observation["source"]
        serialized = json.dumps(bundle)
        self.assertTrue(observation["value"])
        self.assertEqual(source["kind"], "github-actions")
        self.assertEqual(source["conclusion"], "success")
        self.assertEqual(source["run_id"], "12345")
        self.assertEqual(source["run_attempt"], "2")
        self.assertEqual(source["workflow"], "CI")
        self.assertEqual(source["job"], "test")
        self.assertEqual(source["sha"], "abcdef123456")
        self.assertEqual(
            source["run_url"],
            "https://github.com/ptrgiang/trustforge-skills/actions/runs/12345",
        )
        self.assertNotIn("must-not-appear", serialized)
        self.assertNotIn("GITHUB_TOKEN", serialized)

    def test_github_actions_non_success_maps_false(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "1",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW": "CI",
            "GITHUB_JOB": "test",
            "GITHUB_SHA": "abc",
        }
        bundle = collect_github_actions("ci.passed", "failure", environment=env)
        self.assertFalse(bundle["observations"]["ci.passed"]["value"])

    def test_github_actions_fails_closed_outside_actions(self):
        with self.assertRaises(CommitmentEvidenceError):
            collect_github_actions("ci.passed", "success", environment={})

    def test_github_actions_fails_closed_when_required_metadata_missing(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "owner/repo"}
        with self.assertRaises(CommitmentEvidenceError):
            collect_github_actions("ci.passed", "success", environment=env)

    def test_package_manifest_emits_exact_digest_and_manifest_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pyproject.toml"
            raw = b'[project]\nname = "demo"\n'
            path.write_bytes(raw)
            bundle = collect_package_manifest(
                "dependencies.manifest_sha256",
                path,
                observed_at="2026-09-11T15:20:00Z",
            )
            observation = bundle["observations"]["dependencies.manifest_sha256"]
            expected = hashlib.sha256(raw).hexdigest()
            self.assertEqual(observation["value"], expected)
            self.assertEqual(observation["source"]["kind"], "package-manifest")
            self.assertEqual(observation["source"]["manifest_type"], "python-pyproject")
            self.assertEqual(observation["source"]["sha256"], expected)
            self.assertEqual(observation["source"]["size_bytes"], len(raw))

    def test_package_manifest_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requirements.txt"
            path.write_bytes(b"")
            with self.assertRaises(CommitmentEvidenceError):
                collect_package_manifest("manifest", path)

    def test_api_diff_true_when_operations_only_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            before.write_text('{"paths":{"/users":{"get":{}}}}', encoding="utf-8")
            after.write_text('{"paths":{"/users":{"get":{}},"/health":{"get":{}}}}', encoding="utf-8")
            bundle = collect_api_diff("api.no_removed_operations", before, after)
            observation = bundle["observations"]["api.no_removed_operations"]
            source = observation["source"]
            self.assertTrue(observation["value"])
            self.assertEqual(source["kind"], "api-diff")
            self.assertEqual(source["removed_operation_count"], 0)
            self.assertEqual(source["added_operation_count"], 1)
            self.assertFalse(source["operation_names_captured"])
            self.assertNotIn("/users", json.dumps(bundle))
            self.assertNotIn("/health", json.dumps(bundle))

    def test_api_diff_false_when_operation_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            before.write_text('{"paths":{"/users":{"get":{},"post":{}}}}', encoding="utf-8")
            after.write_text('{"paths":{"/users":{"get":{}}}}', encoding="utf-8")
            bundle = collect_api_diff("api.no_removed_operations", before, after)
            observation = bundle["observations"]["api.no_removed_operations"]
            self.assertFalse(observation["value"])
            self.assertEqual(observation["source"]["removed_operation_count"], 1)

    def test_api_diff_rejects_non_openapi_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.json"
            after = Path(tmp) / "after.json"
            before.write_text('{"ok":true}', encoding="utf-8")
            after.write_text('{"ok":true}', encoding="utf-8")
            with self.assertRaises(CommitmentEvidenceError):
                collect_api_diff("api", before, after)

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
