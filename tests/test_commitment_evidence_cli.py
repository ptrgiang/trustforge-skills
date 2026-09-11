from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from trustforge.cli import build_parser, main


class CommitmentEvidenceCliTests(unittest.TestCase):
    def test_pytest_parser_preserves_args_after_separator(self):
        args = build_parser().parse_args(
            [
                "evidence",
                "pytest",
                "--key",
                "tests.passed",
                "--python",
                "python3",
                "--timeout",
                "42",
                "--",
                "tests/test_api.py",
                "-q",
            ]
        )
        self.assertEqual(args.evidence_command, "pytest")
        self.assertEqual(args.key, "tests.passed")
        self.assertEqual(args.python_executable, "python3")
        self.assertEqual(args.timeout, 42.0)
        self.assertEqual(args.pytest_args, ["--", "tests/test_api.py", "-q"])

    def test_pytest_cli_calls_collector_and_emits_bundle(self):
        expected = {
            "schema_version": "0.2",
            "observations": {
                "tests.passed": {
                    "value": True,
                    "observed_at": "2026-09-11T14:45:00Z",
                    "source": {"kind": "pytest", "exit_code": 0},
                }
            },
        }
        output = io.StringIO()
        with patch("trustforge.cli.collect_pytest", return_value=expected) as collector:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "evidence",
                        "pytest",
                        "--key",
                        "tests.passed",
                        "--python",
                        "python3",
                        "--observed-at",
                        "2026-09-11T14:45:00Z",
                        "--timeout",
                        "42",
                        "--",
                        "tests/test_api.py",
                        "-q",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        collector.assert_called_once_with(
            "tests.passed",
            ["tests/test_api.py", "-q"],
            python_executable="python3",
            observed_at="2026-09-11T14:45:00Z",
            timeout_seconds=42.0,
        )

    def test_github_actions_parser_accepts_explicit_conclusion(self):
        args = build_parser().parse_args(
            [
                "evidence",
                "github-actions",
                "--key",
                "ci.passed",
                "--conclusion",
                "success",
            ]
        )
        self.assertEqual(args.evidence_command, "github-actions")
        self.assertEqual(args.key, "ci.passed")
        self.assertEqual(args.conclusion, "success")

    def test_github_actions_cli_uses_runtime_environment(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "99",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW": "CI",
            "GITHUB_JOB": "test",
            "GITHUB_SHA": "abc123",
            "GITHUB_TOKEN": "secret-token",
        }
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True):
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "evidence",
                        "github-actions",
                        "--key",
                        "ci.passed",
                        "--conclusion",
                        "success",
                        "--observed-at",
                        "2026-09-11T14:55:00Z",
                    ]
                )
        self.assertEqual(exit_code, 0)
        report = json.loads(output.getvalue())
        observation = report["observations"]["ci.passed"]
        self.assertTrue(observation["value"])
        self.assertEqual(observation["source"]["kind"], "github-actions")
        self.assertEqual(observation["source"]["run_id"], "99")
        self.assertNotIn("secret-token", output.getvalue())

    def test_package_manifest_cli_calls_collector(self):
        expected = {
            "schema_version": "0.2",
            "observations": {
                "dependencies.manifest_sha256": {
                    "value": "abc",
                    "observed_at": "2026-09-11T15:20:00Z",
                    "source": {"kind": "package-manifest", "sha256": "abc"},
                }
            },
        }
        output = io.StringIO()
        with patch("trustforge.cli.collect_package_manifest", return_value=expected) as collector:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "evidence",
                        "package-manifest",
                        "--input",
                        "pyproject.toml",
                        "--observed-at",
                        "2026-09-11T15:20:00Z",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        collector.assert_called_once_with(
            "dependencies.manifest_sha256",
            "pyproject.toml",
            observed_at="2026-09-11T15:20:00Z",
        )

    def test_api_diff_cli_calls_collector(self):
        expected = {
            "schema_version": "0.2",
            "observations": {
                "api.no_removed_operations": {
                    "value": True,
                    "observed_at": "2026-09-11T15:20:00Z",
                    "source": {"kind": "api-diff", "removed_operation_count": 0},
                }
            },
        }
        output = io.StringIO()
        with patch("trustforge.cli.collect_api_diff", return_value=expected) as collector:
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "evidence",
                        "api-diff",
                        "--before",
                        "before.json",
                        "--after",
                        "after.json",
                        "--observed-at",
                        "2026-09-11T15:20:00Z",
                    ]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        collector.assert_called_once_with(
            "api.no_removed_operations",
            "before.json",
            "after.json",
            observed_at="2026-09-11T15:20:00Z",
        )


if __name__ == "__main__":
    unittest.main()
