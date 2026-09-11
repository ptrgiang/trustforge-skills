from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from trustforge.reprocapsule import build_capsule
from trustforge.reprocapsule_container import replay_container


class FakeDocker:
    def __init__(self, *, run_return_code: int = 1, run_stderr: str = "AssertionError: boom"):
        self.calls: list[list[str]] = []
        self.run_return_code = run_return_code
        self.run_stderr = run_stderr

    def __call__(self, command, **kwargs):
        command = list(command)
        self.calls.append(command)
        if command[:2] == ["docker", "build"]:
            return subprocess.CompletedProcess(command, 0, stdout="built", stderr="")
        if command[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(command, self.run_return_code, stdout="", stderr=self.run_stderr)
        if command[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")


class ReproCapsuleContainerTests(unittest.TestCase):
    def _capsule(self, root: Path) -> Path:
        (root / "app.py").write_text("raise AssertionError('boom')\n", encoding="utf-8")
        spec = root / "spec.yaml"
        spec.write_text(
            "schema_version: '0.1'\n"
            "name: container-demo\n"
            "command: [python, app.py]\n"
            "expected_exit_code: 1\n"
            "expected_failure_signature: 'AssertionError: boom'\n"
            "inputs:\n  - path: app.py\n",
            encoding="utf-8",
        )
        capsule = root / "capsule"
        build_capsule(spec, capsule)
        return capsule

    def test_default_is_integrity_only_and_does_not_touch_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = self._capsule(Path(tmp))
            fake = FakeDocker()
            report = replay_container(capsule, execute=False, runner=fake)
            self.assertEqual(report["decision"], "ready")
            self.assertFalse(report["executed"])
            self.assertFalse(report["container_built"])
            self.assertEqual(fake.calls, [])

    def test_execute_uses_hardened_build_and_runtime_flags_and_reproduces(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = self._capsule(Path(tmp))
            fake = FakeDocker()
            report = replay_container(capsule, execute=True, runner=fake)
            self.assertEqual(report["decision"], "reproduced")
            self.assertTrue(report["executed"])
            self.assertTrue(report["container_built"])
            build = next(call for call in fake.calls if call[:2] == ["docker", "build"])
            run = next(call for call in fake.calls if call[:2] == ["docker", "run"])
            self.assertIn("--network none", " ".join(build))
            joined = " ".join(run)
            self.assertIn("--network none", joined)
            self.assertIn("--read-only", run)
            self.assertIn("--cap-drop ALL", joined)
            self.assertIn("no-new-privileges:true", run)
            self.assertIn("--pids-limit 128", joined)
            self.assertIn("--memory 512m", joined)
            self.assertIn("--cpus 1.0", joined)
            self.assertTrue(report["safety"]["build_network_disabled"])

    def test_divergence_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = self._capsule(Path(tmp))
            fake = FakeDocker(run_return_code=0, run_stderr="all good")
            report = replay_container(capsule, execute=True, runner=fake)
            self.assertEqual(report["decision"], "diverged")
            self.assertFalse(report["exit_code_match"])
            self.assertFalse(report["failure_signature_match"])

    def test_tampered_capsule_blocks_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = self._capsule(Path(tmp))
            (capsule / "inputs" / "app.py").write_text("print('tampered')\n", encoding="utf-8")
            fake = FakeDocker()
            report = replay_container(capsule, execute=True, runner=fake)
            self.assertEqual(report["decision"], "blocked")
            self.assertEqual(report["reason"], "integrity_failed")
            self.assertEqual(fake.calls, [])

    def test_runtime_output_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            capsule = self._capsule(Path(tmp))
            fake = FakeDocker(run_stderr="AssertionError: boom\nAPI_KEY=supersecret")
            report = replay_container(capsule, execute=True, runner=fake)
            self.assertEqual(report["decision"], "reproduced")
            self.assertNotIn("supersecret", report["stderr"])
            self.assertGreaterEqual(report["redactions"], 1)


if __name__ == "__main__":
    unittest.main()
