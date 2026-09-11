from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trustforge.cli import main
from trustforge.commitment_attestation import private_key_pem, public_key_pem


class CommitmentAttestationCliTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        private_key = Ed25519PrivateKey.generate()
        private_path = root / "private.pem"
        public_path = root / "public.pem"
        registry_path = root / "trust.json"
        evidence_path = root / "evidence.json"
        private_path.write_bytes(private_key_pem(private_key))
        public_path.write_bytes(public_key_pem(private_key.public_key()))
        registry_path.write_text(
            json.dumps({
                "schema_version": "0.1",
                "keys": [
                    {
                        "issuer": "ci.example",
                        "key_id": "release-key",
                        "public_key_file": "public.pem",
                    }
                ],
            }),
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps({
                "schema_version": "0.2",
                "observations": {
                    "ci.passed": {
                        "value": True,
                        "observed_at": "2026-09-11T14:00:00Z",
                        "source": {"kind": "github-actions", "run_id": "123"},
                    }
                },
            }),
            encoding="utf-8",
        )
        return private_path, public_path, registry_path, evidence_path

    def test_sign_then_verify_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_path, _, registry_path, evidence_path = self._write_fixture(root)

            signed_output = io.StringIO()
            with redirect_stdout(signed_output):
                sign_code = main([
                    "evidence",
                    "sign",
                    "--input", str(evidence_path),
                    "--key", "ci.passed",
                    "--private-key", str(private_path),
                    "--issuer", "ci.example",
                    "--key-id", "release-key",
                    "--issued-at", "2026-09-11T14:00:10Z",
                    "--expires-at", "2026-09-11T15:00:10Z",
                ])
            self.assertEqual(sign_code, 0)
            signed = json.loads(signed_output.getvalue())
            self.assertIn("attestation", signed["observations"]["ci.passed"])
            signed_path = root / "signed.json"
            signed_path.write_text(json.dumps(signed), encoding="utf-8")

            verify_output = io.StringIO()
            with redirect_stdout(verify_output):
                verify_code = main([
                    "evidence",
                    "verify-attestation",
                    "--input", str(signed_path),
                    "--key", "ci.passed",
                    "--trust-registry", str(registry_path),
                    "--as-of", "2026-09-11T14:30:00Z",
                ])
            self.assertEqual(verify_code, 0)
            verification = json.loads(verify_output.getvalue())
            self.assertTrue(verification["verified"])
            self.assertEqual(verification["issuer"], "ci.example")
            self.assertNotIn("signature", verification)

    def test_verify_command_accepts_trust_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_path, _, registry_path, evidence_path = self._write_fixture(root)
            signed_output = io.StringIO()
            with redirect_stdout(signed_output):
                self.assertEqual(main([
                    "evidence", "sign",
                    "--input", str(evidence_path),
                    "--key", "ci.passed",
                    "--private-key", str(private_path),
                    "--issuer", "ci.example",
                    "--key-id", "release-key",
                    "--issued-at", "2026-09-11T14:00:10Z",
                    "--expires-at", "2026-09-11T15:00:10Z",
                ]), 0)
            signed_path = root / "signed.json"
            signed_path.write_text(signed_output.getvalue(), encoding="utf-8")
            contract_path = root / "contract.json"
            contract_path.write_text(
                json.dumps({
                    "schema_version": "0.2",
                    "commitments": [
                        {
                            "id": "ci-pass",
                            "description": "CI passes with signed evidence",
                            "evidence": {
                                "key": "ci.passed",
                                "truthy": True,
                                "require_attestation": True,
                                "allowed_attestation_issuers": ["ci.example"],
                                "allowed_attestation_key_ids": ["release-key"],
                            },
                        }
                    ],
                }),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([
                    "verify",
                    str(contract_path),
                    "--evidence", str(signed_path),
                    "--trust-registry", str(registry_path),
                    "--as-of", "2026-09-11T14:30:00Z",
                    "--json",
                ])
            self.assertEqual(exit_code, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["completion_state"], "verified_complete")
            self.assertEqual(report["commitments"][0]["attestation"]["key_id"], "release-key")


if __name__ == "__main__":
    unittest.main()
