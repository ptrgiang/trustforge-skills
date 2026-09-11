from __future__ import annotations

import json
import unittest
from pathlib import Path

from trustforge.datalease import DataLeaseError, apply_policy, classify_with_plugins
from trustforge.datalease_adapters import HTTPDataLeaseAdapter
from trustforge.datalease_classifiers import ClassificationFinding, CallableClassifier
from trustforge.datalease_eval import benchmark_file


class EmployeeIdClassifier:
    name = "employee-id-v1"

    def classify(self, path, value):
        if path.endswith("employee_id") and isinstance(value, str):
            return [
                ClassificationFinding(
                    label="sensitivity.internal_id",
                    detector=self.name,
                    confidence=0.98,
                    reason="Organization-specific employee identifier.",
                )
            ]
        return []


class BrokenClassifier:
    name = "broken"

    def classify(self, path, value):
        raise RuntimeError("boom")


class DataLeasePluginTests(unittest.TestCase):
    def test_custom_classifier_can_drive_hard_deny(self) -> None:
        policy = {
            "version": "0.1",
            "purpose": "send summary",
            "default_action": "allow",
            "hard_deny_classifiers": ["secret", "sensitivity.internal_id"],
            "rules": [],
        }
        report = apply_policy(
            policy,
            "send summary",
            {"employee_id": "EMP-123", "status": "active"},
            classifiers=[EmployeeIdClassifier()],
        )

        self.assertEqual(report["output"], {"status": "active"})
        employee_audit = next(
            item for item in report["audit"] if item["path"] == "employee_id"
        )
        self.assertEqual(employee_audit["rule_id"], "hard-deny:sensitivity.internal_id")
        self.assertEqual(
            employee_audit["classifier_evidence"][0]["detector"],
            "employee-id-v1",
        )
        self.assertNotIn("EMP-123", json.dumps(employee_audit))

    def test_callable_classifier_normalizes_string_findings(self) -> None:
        classifier = CallableClassifier(
            "tenant-policy",
            lambda path, value: ["sensitivity.tenant_id"]
            if path == "tenant_id"
            else [],
            confidence=0.91,
        )
        findings = classify_with_plugins(
            "tenant_id",
            "TENANT-1",
            classifiers=[classifier],
        )

        custom = next(
            finding for finding in findings
            if finding.label == "sensitivity.tenant_id"
        )
        self.assertEqual(custom.detector, "tenant-policy")
        self.assertAlmostEqual(custom.confidence, 0.91)

    def test_classifier_failures_fail_closed(self) -> None:
        policy = {
            "version": "0.1",
            "purpose": "send summary",
            "default_action": "allow",
            "rules": [],
        }
        with self.assertRaises(DataLeaseError):
            apply_policy(
                policy,
                "send summary",
                {"status": "active"},
                classifiers=[BrokenClassifier()],
            )

    def test_http_adapter_propagates_custom_classifier(self) -> None:
        policy = {
            "version": "0.1",
            "purpose": "send summary",
            "default_action": "allow",
            "hard_deny_classifiers": ["sensitivity.internal_id"],
            "destinations": {
                "http": {
                    "schemes": ["https"],
                    "hosts": ["support.example.com"],
                    "methods": ["POST"],
                }
            },
            "rules": [],
        }
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            return {"status": 200}

        adapter = HTTPDataLeaseAdapter(
            policy,
            transport,
            classifiers=[EmployeeIdClassifier()],
        )
        adapter.send_json(
            "POST",
            "https://support.example.com/tickets",
            purpose="send summary",
            json_body={"employee_id": "EMP-123", "status": "active"},
        )

        self.assertEqual(calls[0]["json"], {"status": "active"})

    def test_builtin_benchmark_has_explicit_nonperfect_baseline(self) -> None:
        dataset = (
            Path(__file__).resolve().parents[1]
            / "evals"
            / "datalease"
            / "classifier-benchmark.jsonl"
        )
        report = benchmark_file(dataset)

        self.assertEqual(report["samples"], 30)
        self.assertGreaterEqual(report["micro"]["precision"], 0.90)
        self.assertGreaterEqual(report["micro"]["recall"], 0.85)
        self.assertLess(report["exact_match"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
