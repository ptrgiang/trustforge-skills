from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trustforge.datalease import DataLeaseError, apply_files, apply_policy, classify_field, load_policy


POLICY = {
    "version": "0.1",
    "purpose": "send order summary to support tool",
    "default_action": "deny",
    "hard_deny_classifiers": ["secret"],
    "rules": [
        {
            "id": "order-summary",
            "paths": ["order.id", "order.status", "items.*.sku", "items.*.quantity"],
            "action": "allow",
            "reason": "Required to explain order state.",
        },
        {
            "id": "customer-email",
            "paths": ["customer.email"],
            "classifiers": ["pii.email"],
            "action": "redact",
            "strategy": "email_domain",
            "reason": "Domain context is sufficient; local-part is unnecessary.",
        },
    ],
}

PAYLOAD = {
    "order": {"id": "A-100", "status": "shipped", "total": 39.5},
    "customer": {
        "email": "alice@example.com",
        "phone": "+1 202-555-0187",
        "full_name": "Alice Example",
    },
    "items": [
        {"sku": "SKU-1", "quantity": 2, "cost": 10.0},
        {"sku": "SKU-2", "quantity": 1, "cost": 19.5},
    ],
    "internal": {"api_token": "super-secret-token"},
}


class DataLeaseTests(unittest.TestCase):
    def test_projects_minimum_necessary_fields(self) -> None:
        report = apply_policy(POLICY, "send order summary to support tool", PAYLOAD)

        self.assertEqual(report["decision"], "projected")
        self.assertEqual(
            report["output"],
            {
                "order": {"id": "A-100", "status": "shipped"},
                "customer": {"email": "***@example.com"},
                "items": [
                    {"sku": "SKU-1", "quantity": 2},
                    {"sku": "SKU-2", "quantity": 1},
                ],
            },
        )
        self.assertGreater(report["summary"]["denied"], 0)
        self.assertEqual(report["summary"]["redacted"], 1)

    def test_purpose_mismatch_denies_whole_transfer(self) -> None:
        report = apply_policy(POLICY, "send raw customer record to analytics vendor", PAYLOAD)

        self.assertEqual(report["decision"], "denied")
        self.assertIsNone(report["output"])
        self.assertEqual(report["audit"][0]["rule_id"], "purpose-binding")

    def test_hard_deny_secret_cannot_be_overridden_by_path_allow(self) -> None:
        policy = {
            "version": "0.1",
            "purpose": "debug",
            "default_action": "deny",
            "hard_deny_classifiers": ["secret"],
            "rules": [
                {"id": "broad", "paths": ["internal.*"], "action": "allow"},
            ],
        }
        report = apply_policy(policy, "debug", {"internal": {"api_token": "do-not-share"}})

        self.assertEqual(report["output"], None)
        self.assertEqual(report["audit"][0]["rule_id"], "hard-deny:secret")

    def test_audit_never_contains_raw_secret_value(self) -> None:
        report = apply_policy(POLICY, "send order summary to support tool", PAYLOAD)
        serialized = json.dumps(report["audit"])

        self.assertNotIn("super-secret-token", serialized)
        self.assertNotIn("alice@example.com", serialized)

    def test_classifier_detects_email_phone_and_ip(self) -> None:
        self.assertIn("pii.email", classify_field("contact", "alice@example.com"))
        self.assertIn("pii.phone", classify_field("contact", "+1 202-555-0187"))
        self.assertIn("network.ip", classify_field("client.ip", "192.0.2.10"))

    def test_loads_yaml_policy_and_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy_path = root / "policy.yaml"
            input_path = root / "payload.json"
            policy_path.write_text(
                """
version: "0.1"
purpose: send order summary to support tool
default_action: deny
hard_deny_classifiers:
  - secret
rules:
  - id: order
    paths:
      - order.id
    action: allow
""".strip(),
                encoding="utf-8",
            )
            input_path.write_text(json.dumps(PAYLOAD), encoding="utf-8")

            report = apply_files(policy_path, input_path, "send order summary to support tool")
            self.assertEqual(report["output"], {"order": {"id": "A-100"}})

    def test_invalid_policy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text('{"version": "0.1", "rules": []}', encoding="utf-8")
            with self.assertRaises(DataLeaseError):
                load_policy(path)


if __name__ == "__main__":
    unittest.main()
