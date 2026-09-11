from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from trustforge.reprocapsule import (
    ReproCapsuleError,
    build_capsule,
    replay_capsule,
    sanitize_trace,
    verify_integrity,
)


class ReproCapsuleTests(unittest.TestCase):
    def test_sanitize_trace_redacts_common_secrets(self):
        text = "API_KEY=abc123\nAuthorization: Bearer token-value\nghp_abcdefghijklmnopqrstuvwxyz123456\n"
        sanitized, count = sanitize_trace(text)
        self.assertNotIn("abc123", sanitized)
        self.assertNotIn("token-value", sanitized)
        self.assertNotIn("ghp_", sanitized)
        self.assertGreaterEqual(count, 3)

    def test_build_capsule_hashes_and_copies_inputs_without_env_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "input.json").write_text('{"x": 1}\n', encoding="utf-8")
            (root / "trace.txt").write_text("password=hunter2\nboom\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "schema_version: '0.1'\n"
                "name: demo\n"
                "command: [python, app.py, input.json]\n"
                "expected_exit_code: 1\n"
                "trace_file: trace.txt\n"
                "inputs:\n  - path: input.json\n"
                "environment:\n  include: [REPRO_TEST_SECRET]\n",
                encoding="utf-8",
            )
            os.environ["REPRO_TEST_SECRET"] = "do-not-copy-me"
            output = root / "capsule"
            report = build_capsule(spec, output)
            serialized = json.dumps(report)
            self.assertNotIn("do-not-copy-me", serialized)
            self.assertTrue(report["environment_presence"]["REPRO_TEST_SECRET"]["present"])
            self.assertEqual(report["inputs"][0]["sha256"], "936353965b4ba9180e3acb781d81aa634390ac95fd2874a9cbc4c4846b49fbd4")
            self.assertTrue((output / "inputs" / "input.json").is_file())
            self.assertNotIn("hunter2", (output / "trace.txt").read_text(encoding="utf-8"))
            self.assertFalse(report["safety"]["raw_environment_values_included"])
            self.assertFalse(report["safety"]["command_executed_during_build"])

    def test_replay_requires_explicit_execute_and_reproduces_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text(
                "raise RuntimeError('expected boom')\n",
                encoding="utf-8",
            )
            spec = root / "spec.yaml"
            spec.write_text(
                "schema_version: '0.1'\n"
                "name: replay-demo\n"
                "command: [python, app.py]\n"
                "expected_exit_code: 1\n"
                "expected_failure_signature: 'RuntimeError: expected boom'\n"
                "inputs:\n  - path: app.py\n",
                encoding="utf-8",
            )
            capsule = root / "capsule"
            build_capsule(spec, capsule)

            ready = replay_capsule(capsule)
            self.assertEqual(ready["decision"], "ready")
            self.assertFalse(ready["executed"])

            replay = replay_capsule(capsule, execute=True)
            self.assertEqual(replay["decision"], "reproduced")
            self.assertTrue(replay["executed"])
            self.assertTrue(replay["exit_code_match"])
            self.assertTrue(replay["failure_signature_match"])

    def test_replay_blocks_when_packaged_input_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "name: tamper-demo\n"
                "command: [python, app.py]\n"
                "expected_exit_code: 1\n"
                "inputs:\n  - path: app.py\n",
                encoding="utf-8",
            )
            capsule = root / "capsule"
            build_capsule(spec, capsule)
            (capsule / "inputs" / "app.py").write_text("print('changed')\n", encoding="utf-8")

            integrity = verify_integrity(capsule)
            self.assertEqual(integrity["decision"], "blocked")
            replay = replay_capsule(capsule, execute=True)
            self.assertEqual(replay["decision"], "blocked")
            self.assertFalse(replay["executed"])
            self.assertEqual(replay["reason"], "integrity_check_failed")

    def test_replay_reports_divergence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("raise RuntimeError('different')\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "name: diverge-demo\n"
                "command: [python, app.py]\n"
                "expected_exit_code: 1\n"
                "expected_failure_signature: 'RuntimeError: expected'\n"
                "inputs:\n  - path: app.py\n",
                encoding="utf-8",
            )
            capsule = root / "capsule"
            build_capsule(spec, capsule)
            replay = replay_capsule(capsule, execute=True)
            self.assertEqual(replay["decision"], "diverged")
            self.assertTrue(replay["exit_code_match"])
            self.assertFalse(replay["failure_signature_match"])

    def test_rejects_sensitive_input_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "name: demo\ncommand: [python, app.py]\ninputs:\n  - path: .env\n",
                encoding="utf-8",
            )
            with self.assertRaises(ReproCapsuleError):
                build_capsule(spec, root / "capsule")

    def test_rejects_secret_like_command_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.yaml"
            spec.write_text(
                "name: demo\ncommand: [curl, '--api-key=supersecret', https://example.com]\n",
                encoding="utf-8",
            )
            with self.assertRaises(ReproCapsuleError):
                build_capsule(spec, root / "capsule")

    def test_rejects_parent_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.yaml"
            spec.write_text(
                "name: demo\ncommand: [python, app.py]\ninputs:\n  - path: ../outside.txt\n",
                encoding="utf-8",
            )
            with self.assertRaises(ReproCapsuleError):
                build_capsule(spec, root / "capsule")


if __name__ == "__main__":
    unittest.main()
