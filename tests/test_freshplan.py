from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trustforge.freshplan import FreshPlanError, evaluate, evaluate_file


AS_OF = "2026-09-11T09:30:00Z"


def sample_plan():
    return {
        "version": "0.1",
        "facts": [
            {
                "id": "inventory",
                "observed_at": "2026-09-11T09:20:00Z",
                "ttl_seconds": 600,
                "provenance": {"source": "sp-api", "reference": "inventory-summary"},
                "value": {"secret_raw_value": "must-not-appear"},
            },
            {
                "id": "fx",
                "observed_at": "2026-09-11T09:20:00Z",
                "ttl_seconds": 3600,
                "provenance": {"source": "fx-api"},
            },
        ],
        "nodes": [
            {"id": "reorder", "depends_on": {"facts": ["inventory"]}},
            {"id": "purchase", "depends_on": {"nodes": ["reorder"]}},
            {"id": "price", "depends_on": {"facts": ["fx"]}},
        ],
    }


class FreshPlanTests(unittest.TestCase):
    def test_selective_invalidation_propagates_only_affected_branch(self):
        report = evaluate(sample_plan(), as_of=AS_OF)
        self.assertEqual(report["decision"], "replan_required")
        self.assertEqual(report["stale_facts"], ["inventory"])
        self.assertEqual(report["replan_order"], ["reorder", "purchase"])
        self.assertEqual(report["unaffected_nodes"], ["price"])
        self.assertEqual(
            report["invalidated_nodes"][1]["root_stale_facts"],
            ["inventory"],
        )

    def test_all_fresh_requires_no_replan(self):
        report = evaluate(sample_plan(), as_of="2026-09-11T09:25:00Z")
        self.assertEqual(report["decision"], "fresh")
        self.assertEqual(report["replan_order"], [])
        self.assertEqual(set(report["unaffected_nodes"]), {"reorder", "purchase", "price"})

    def test_future_observation_fails_closed_as_stale(self):
        plan = sample_plan()
        plan["facts"][0]["observed_at"] = "2026-09-11T10:00:00Z"
        report = evaluate(plan, as_of=AS_OF)
        inventory = next(item for item in report["facts"] if item["id"] == "inventory")
        self.assertEqual(inventory["status"], "stale")
        self.assertEqual(inventory["reason"], "observed_at_in_future")
        self.assertIn("reorder", report["replan_order"])

    def test_earliest_validity_bound_wins(self):
        plan = sample_plan()
        plan["facts"][1]["ttl_seconds"] = 7200
        plan["facts"][1]["valid_until"] = "2026-09-11T09:25:00Z"
        report = evaluate(plan, as_of=AS_OF)
        self.assertEqual(report["stale_facts"], ["fx", "inventory"])
        self.assertIn("price", report["replan_order"])

    def test_unknown_dependency_is_rejected(self):
        plan = sample_plan()
        plan["nodes"][0]["depends_on"]["facts"] = ["missing"]
        with self.assertRaises(FreshPlanError):
            evaluate(plan, as_of=AS_OF)

    def test_cycles_are_rejected(self):
        plan = {
            "version": "0.1",
            "facts": [],
            "nodes": [
                {"id": "a", "depends_on": {"nodes": ["b"]}},
                {"id": "b", "depends_on": {"nodes": ["a"]}},
            ],
        }
        with self.assertRaises(FreshPlanError):
            evaluate(plan, as_of=AS_OF)

    def test_report_does_not_copy_raw_fact_values(self):
        report = evaluate(sample_plan(), as_of=AS_OF)
        self.assertNotIn("secret_raw_value", str(report))
        self.assertNotIn("value", report["facts"][0])

    def test_yaml_file_loading(self):
        text = """
version: "0.1"
facts:
  - id: catalog
    observed_at: 2026-09-11T09:20:00Z
    ttl_seconds: 3600
    provenance:
      source: catalog-api
nodes:
  - id: listing
    depends_on:
      facts: [catalog]
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.yaml"
            path.write_text(text, encoding="utf-8")
            report = evaluate_file(path, as_of=AS_OF)
        self.assertEqual(report["decision"], "fresh")


if __name__ == "__main__":
    unittest.main()
