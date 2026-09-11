from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trustforge.reprocapsule import build_capsule
from trustforge.reprocapsule_export import export_container


class ReproCapsuleExportTests(unittest.TestCase):
    def test_exports_verified_capsule_to_docker_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "schema_version: '0.1'\n"
                "name: export-demo\n"
                "command: [python, app.py]\n"
                "expected_exit_code: 1\n"
                "inputs:\n  - path: app.py\n",
                encoding="utf-8",
            )
            capsule = root / "capsule"
            build_capsule(spec, capsule)
            output = root / "container"
            report = export_container(capsule, output)

            self.assertEqual(report["decision"], "exported")
            self.assertTrue(report["base_image"].startswith("python:"))
            self.assertTrue((output / "Dockerfile").is_file())
            self.assertTrue((output / ".devcontainer" / "devcontainer.json").is_file())
            self.assertTrue((output / "inputs" / "app.py").is_file())
            dockerfile = (output / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("USER repro", dockerfile)
            self.assertIn('CMD ["python", "app.py"]', dockerfile)
            export_manifest = json.loads((output / "container-export.json").read_text(encoding="utf-8"))
            self.assertEqual(export_manifest, report)
            self.assertFalse(report["safety"]["container_built_during_export"])
            self.assertFalse(report["safety"]["container_executed_during_export"])

    def test_blocks_export_when_capsule_is_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
            spec = root / "spec.yaml"
            spec.write_text(
                "name: export-demo\ncommand: [python, app.py]\nexpected_exit_code: 1\ninputs:\n  - path: app.py\n",
                encoding="utf-8",
            )
            capsule = root / "capsule"
            build_capsule(spec, capsule)
            (capsule / "inputs" / "app.py").write_text("print('tampered')\n", encoding="utf-8")
            output = root / "container"
            report = export_container(capsule, output)
            self.assertEqual(report["decision"], "blocked")
            self.assertEqual(report["reason"], "integrity_failed")
            self.assertFalse((output / "Dockerfile").exists())


if __name__ == "__main__":
    unittest.main()
