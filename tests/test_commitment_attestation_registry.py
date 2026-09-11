import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trustforge.commitment_attestation import (
    AttestationError,
    load_trust_registry,
    public_key_pem,
)


class CommitmentAttestationRegistryTests(unittest.TestCase):
    def test_loads_relative_public_key_file(self):
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ci.pub.pem").write_bytes(public_key_pem(private_key.public_key()))
            (root / "trust.json").write_text(
                json.dumps({
                    "schema_version": "0.1",
                    "keys": [
                        {
                            "issuer": "ci.example",
                            "key_id": "release-key",
                            "public_key_file": "ci.pub.pem",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            trusted = load_trust_registry(root / "trust.json")
            self.assertIn(("ci.example", "release-key"), trusted)

    def test_duplicate_identity_fails_closed(self):
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ci.pub.pem").write_bytes(public_key_pem(private_key.public_key()))
            entry = {
                "issuer": "ci.example",
                "key_id": "release-key",
                "public_key_file": "ci.pub.pem",
            }
            (root / "trust.json").write_text(
                json.dumps({"schema_version": "0.1", "keys": [entry, entry]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AttestationError, "duplicate trust registry key"):
                load_trust_registry(root / "trust.json")

    def test_non_ed25519_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.pem").write_text("not a pem", encoding="utf-8")
            (root / "trust.json").write_text(
                json.dumps({
                    "schema_version": "0.1",
                    "keys": [
                        {
                            "issuer": "ci.example",
                            "key_id": "release-key",
                            "public_key_file": "bad.pem",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            with self.assertRaises(AttestationError):
                load_trust_registry(root / "trust.json")

    def test_parent_path_escape_fails_closed(self):
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_dir = root / "registry"
            registry_dir.mkdir()
            (root / "outside.pem").write_bytes(public_key_pem(private_key.public_key()))
            (registry_dir / "trust.json").write_text(
                json.dumps({
                    "schema_version": "0.1",
                    "keys": [
                        {
                            "issuer": "ci.example",
                            "key_id": "release-key",
                            "public_key_file": "../outside.pem",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AttestationError, "must stay inside"):
                load_trust_registry(registry_dir / "trust.json")

    def test_absolute_public_key_path_fails_closed(self):
        private_key = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key_path = root / "outside.pem"
            key_path.write_bytes(public_key_pem(private_key.public_key()))
            registry_dir = root / "registry"
            registry_dir.mkdir()
            (registry_dir / "trust.json").write_text(
                json.dumps({
                    "schema_version": "0.1",
                    "keys": [
                        {
                            "issuer": "ci.example",
                            "key_id": "release-key",
                            "public_key_file": str(key_path.resolve()),
                        }
                    ],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AttestationError, "must be relative"):
                load_trust_registry(registry_dir / "trust.json")


if __name__ == "__main__":
    unittest.main()
