from __future__ import annotations

import unittest

from trustforge.freshplan import FreshPlanError, evaluate
from trustforge.freshplan_refresh import build_refresh_requests, build_plan_patch
from trustforge.freshplan_benchmark import benchmark, generate_plan


AS_OF = "2026-09-11T09:30:00Z"


def policy_plan():
    return {
        "version": "0.1",
        "freshness_policies": {
            "volatile": {
                "refresh_after_seconds": 300,
                "expire_after_seconds": 900,
            }
        },
        "facts": [
            {
                "id": "inventory",
                "observed_at": "2026-09-11T09:20:00Z",
                "freshness_policy": "volatile",
                "provenance": {"source": "inventory-api"},
                "refresh": {"adapter": "inventory-api"},
            }
        ],
        "nodes": [
            {"id": "reorder", "depends_on": {"facts": ["inventory"]}},
        ],
    }


class FreshPlanPolicyTests(unittest.TestCase):
    def test_policy_only_fact_can_be_fresh_without_explicit_ttl(self):
        report = evaluate(policy_plan(), as_of="2026-09-11T09:24:00Z")
        self.assertEqual(report["decision"], "fresh")
        self.assertEqual(report["facts"][0]["status"], "fresh")

    def test_refresh_due_does_not_invalidate_plan(self):
        report = evaluate(policy_plan(), as_of="2026-09-11T09:26:00Z")
        self.assertEqual(report["decision"], "refresh_recommended")
        self.assertEqual(report["refresh_due_facts"], ["inventory"])
        self.assertEqual(report["replan_order"], [])

        requests = build_refresh_requests(policy_plan(), as_of="2026-09-11T09:26:00Z")
        self.assertEqual(requests["summary"]["refresh_due_facts"], 1)
        self.assertEqual(requests["requests"][0]["current"]["status"], "refresh_due")
        self.assertEqual(requests["requests"][0]["fact_id"], "inventory")

    def test_hard_expiry_still_invalidates(self):
        report = evaluate(policy_plan(), as_of="2026-09-11T09:36:00Z")
        self.assertEqual(report["decision"], "replan_required")
        self.assertEqual(report["stale_facts"], ["inventory"])
        self.assertEqual(report["replan_order"], ["reorder"])

    def test_explicit_ttl_can_make_policy_fact_expire_earlier(self):
        plan = policy_plan()
        plan["facts"][0]["ttl_seconds"] = 120
        report = evaluate(plan, as_of="2026-09-11T09:23:00Z")
        self.assertEqual(report["facts"][0]["status"], "stale")

    def test_unknown_policy_is_rejected(self):
        plan = policy_plan()
        plan["facts"][0]["freshness_policy"] = "missing"
        with self.assertRaises(FreshPlanError):
            evaluate(plan, as_of=AS_OF)

    def test_invalid_policy_window_is_rejected(self):
        plan = policy_plan()
        plan["freshness_policies"]["volatile"]["refresh_after_seconds"] = 1000
        with self.assertRaises(FreshPlanError):
            evaluate(plan, as_of=AS_OF)

    def test_policy_bound_replacement_can_omit_ttl(self):
        plan = policy_plan()
        evidence = {
            "version": "0.1",
            "replacements": [
                {
                    "fact_id": "inventory",
                    "evidence_id": "inventory-refresh-1",
                    "observed_at": "2026-09-11T09:29:00Z",
                    "provenance": {"source": "inventory-api"},
                    "change": "unchanged",
                }
            ],
        }
        patch = build_plan_patch(plan, evidence, as_of=AS_OF)
        self.assertIn(patch["decision"], {"no_change", "resumable"})
        self.assertEqual(patch["after"]["stale_facts"], [])


class FreshPlanBenchmarkTests(unittest.TestCase):
    def test_generator_builds_requested_graph(self):
        plan = generate_plan(250)
        self.assertEqual(len(plan["nodes"]), 250)
        self.assertIn("freshness_policies", plan)

    def test_benchmark_reports_structural_metrics(self):
        report = benchmark([100, 500], repeats=1)
        self.assertEqual([case["nodes"] for case in report["cases"]], [100, 500])
        self.assertGreater(report["largest_case"]["nodes_per_second"], 0)
        self.assertGreater(report["largest_case"]["invalidated_nodes"], 0)


if __name__ == "__main__":
    unittest.main()
