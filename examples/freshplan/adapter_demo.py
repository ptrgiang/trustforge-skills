from __future__ import annotations

from pathlib import Path

from trustforge.freshplan import load_plan
from trustforge.freshplan_refresh import CallableRefreshAdapter, dumps, refresh_with_adapters


AS_OF = "2026-09-11T09:30:00Z"


def refresh_inventory(request):
    assert request["fact_id"] == "inventory"
    assert "value" not in request["current"]
    return {
        "fact_id": "inventory",
        "evidence_id": "demo:inventory:20260911T0929Z",
        "observed_at": "2026-09-11T09:29:00Z",
        "ttl_seconds": 900,
        "provenance": {
            "source": "demo-inventory-api",
            "reference": request["reference"] or "inventory:SKU-1",
        },
        "change": "changed",
    }


plan_path = Path(__file__).with_name("refreshable-order.yaml")
plan = load_plan(plan_path)
patch = refresh_with_adapters(
    plan,
    {"inventory-api": CallableRefreshAdapter("inventory-api", refresh_inventory)},
    as_of=AS_OF,
)
print(dumps(patch))
