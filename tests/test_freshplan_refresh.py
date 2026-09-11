from __future__ import annotations

import copy
import unittest

from trustforge.freshplan_refresh import (
    CallableRefreshAdapter,
    FreshPlanRefreshError,
    build_plan_patch,
    build_refresh_requests,
    normalize_replacement_evidence,
    refresh_with_adapters,
    run_refresh_adapters,
)


AS_OF = "2026-09-11T09:30:00Z"


def sample_plan():
    return {
        "version": "0.1",
        "facts": [
            {
                "id": "inventory",
                "observed_at": "2026-09-11T09:00:00Z",
                "ttl_seconds": 900,
                "provenance": {"source": "sp-api", "reference": "inventory-summary"},
                "refresh": {"adapter": "inventory-api", "reference": "inventory:SKU-1"},
                "value": {"raw_secret": "must-not-leak"},
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


def replacement(change="changed", *, observed_at="2026-09-11T09:29:00Z"):
    return {
        "version": "0.1",
        "replacements": [
            {
                "fact_id": "inventory",
                "evidence_id": "evidence:inventory:20260911T0929Z",
                "observed_at": observed_at,
                "ttl_seconds": 900,
                "provenance": {
                    "source": "sp-api",
                    "reference": "inventory-summary:refresh-2",
                },
                "change": change,
            }
        ],
    }


class FreshPlanRefreshTests(unittest.TestCase):
    def test_refresh_request_contains_no_raw_fact_value(self):
        report = build_refresh_requests(sample_plan(), as_of=AS_OF)
        self.assertEqual(report["decision"], "refresh_required")
        self.assertEqual(report["requests"][0]["fact_id"], "inventory")
        self.assertEqual(report["requests"][0]["adapter"], "inventory-api")
        self.assertNotIn("must-not-leak", str(report))
        self.assertNotIn("value", report["requests"][0]["current"])

    def test_changed_replacement_replans_only_affected_branch(self):
        patch = build_plan_patch(sample_plan(), replacement("changed"), as_of=AS_OF)
        self.assertEqual(patch["decision"], "replan_required")
        self.assertEqual(patch["replan_order"], ["reorder", "purchase"])
        self.assertEqual(patch["resume_nodes"], [])
        self.assertEqual(patch["unaffected_nodes"], ["price"])
        self.assertEqual([item["op"] for item in patch["operations"]], ["replan", "replan"])

    def test_unknown_change_fails_safe_to_replan(self):
        patch = build_plan_patch(sample_plan(), replacement("unknown"), as_of=AS_OF)
        self.assertEqual(patch["decision"], "replan_required")
        self.assertEqual(patch["replan_order"], ["reorder", "purchase"])

    def test_unchanged_replacement_resumes_previous_branch(self):
        patch = build_plan_patch(sample_plan(), replacement("unchanged"), as_of=AS_OF)
        self.assertEqual(patch["decision"], "resumable")
        self.assertEqual(patch["resume_nodes"], ["reorder", "purchase"])
        self.assertEqual(patch["replan_order"], [])
        self.assertEqual(patch["unaffected_nodes"], ["price"])

    def test_replacement_that_is_still_stale_keeps_branch_blocked(self):
        evidence = replacement("unchanged", observed_at="2026-09-11T09:00:00Z")
        patch = build_plan_patch(sample_plan(), evidence, as_of=AS_OF)
        self.assertEqual(patch["decision"], "blocked")
        self.assertEqual(patch["blocked_nodes"], ["reorder", "purchase"])
        self.assertEqual(patch["resume_nodes"], [])

    def test_replacement_evidence_rejects_raw_value_fields(self):
        evidence = replacement()
        evidence["replacements"][0]["value"] = {"inventory": 7}
        with self.assertRaises(FreshPlanRefreshError):
            normalize_replacement_evidence(evidence)

    def test_replacement_change_is_required(self):
        evidence = replacement()
        del evidence["replacements"][0]["change"]
        with self.assertRaises(FreshPlanRefreshError):
            normalize_replacement_evidence(evidence)

    def test_adapter_receives_value_free_request_and_returns_evidence(self):
        seen = {}

        def refresh(request):
            seen.update(copy.deepcopy(request))
            return replacement("changed")["replacements"][0]

        evidence = run_refresh_adapters(
            sample_plan(),
            {"inventory-api": CallableRefreshAdapter("inventory-api", refresh)},
            as_of=AS_OF,
        )
        self.assertEqual(evidence["replacements"][0]["fact_id"], "inventory")
        self.assertNotIn("must-not-leak", str(seen))

    def test_adapter_failure_is_fail_closed(self):
        def broken(_request):
            raise RuntimeError("upstream failed")

        with self.assertRaises(FreshPlanRefreshError):
            run_refresh_adapters(
                sample_plan(),
                {"inventory-api": CallableRefreshAdapter("inventory-api", broken)},
                as_of=AS_OF,
            )

    def test_missing_adapter_registration_is_rejected(self):
        with self.assertRaises(FreshPlanRefreshError):
            run_refresh_adapters(sample_plan(), {}, as_of=AS_OF)

    def test_adapter_cannot_return_evidence_for_another_fact(self):
        def wrong(_request):
            item = replacement("changed")["replacements"][0]
            item["fact_id"] = "fx"
            return item

        with self.assertRaises(FreshPlanRefreshError):
            run_refresh_adapters(
                sample_plan(),
                {"inventory-api": CallableRefreshAdapter("inventory-api", wrong)},
                as_of=AS_OF,
            )

    def test_refresh_with_adapters_emits_patch_not_raw_plan(self):
        def refresh(_request):
            return replacement("changed")["replacements"][0]

        patch = refresh_with_adapters(
            sample_plan(),
            {"inventory-api": CallableRefreshAdapter("inventory-api", refresh)},
            as_of=AS_OF,
        )
        self.assertEqual(patch["replan_order"], ["reorder", "purchase"])
        self.assertNotIn("must-not-leak", str(patch))


if __name__ == "__main__":
    unittest.main()
