from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trustforge.reprocapsule_eval import ReproCapsuleBenchmarkError, benchmark_file


class ReproCapsuleBenchmarkTests(unittest.TestCase):
    def test_adversarial_fixture_meets_explicit_baseline(self):
        report = benchmark_file("evals/reprocapsule/redaction-benchmark.jsonl")
        self.assertGreaterEqual(report["secret_cases"], 10)
        self.assertGreaterEqual(report["clean_cases"], 5)
        self.assertEqual(report["secret_recall"], 0.9)
        self.assertEqual(report["clean_specificity"], 0.833333)
        self.assertEqual(
            report["failed_case_ids"],
            ["refresh-token-json", "clean-bearer-word"],
        )

    def test_reports_failed_case_ids_without_echoing_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "benchmark.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "id": "unsupported-secret",
                        "text": "opaque credential value-should-disappear",
                        "secret_markers": ["value-should-disappear"],
                        "preserve_markers": ["opaque credential"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            report = benchmark_file(dataset)
            serialized = json.dumps(report)
            self.assertEqual(report["secret_recall"], 0.0)
            self.assertEqual(report["failed_case_ids"], ["unsupported-secret"])
            self.assertNotIn("value-should-disappear", serialized)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "benchmark.jsonl"
            row = {"id": "same", "text": "safe", "preserve_markers": ["safe"]}
            dataset.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(ReproCapsuleBenchmarkError):
                benchmark_file(dataset)


if __name__ == "__main__":
    unittest.main()
