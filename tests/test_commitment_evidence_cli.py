from __future__ import annotations

import io
import json
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


if __name__ == "__main__":
    unittest.main()
