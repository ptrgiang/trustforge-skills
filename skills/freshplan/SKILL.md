---
name: freshplan
description: Detect aging/stale facts in long-running AI-agent plans, request replacement evidence, and emit minimal control patches for only the affected plan branches.
license: Apache-2.0
metadata:
  trustforge:
    maturity: experimental
    category: reliability
    destructive: false
---

# FreshPlan

Use FreshPlan when an agent plan may outlive the facts that justified it: inventory snapshots, prices, approvals, schedules, search results, API responses, feature flags, availability, or other time-sensitive evidence.

## Goal

Turn "this plan was valid when I made it" into an explicit freshness and recovery protocol:

```text
facts + provenance + freshness policy
              ↓
        FreshPlan graph
              ↓
   fresh / refresh_due / stale
              ↓
     refresh request metadata
              ↓
       replacement evidence
              ↓
  blocked / replan / resume patch
```

FreshPlan reports control metadata rather than raw fact values.

## Fact contract

Facts can use explicit hard bounds (`ttl_seconds`, `valid_until`) or a named plan-level policy:

```yaml
version: "0.1"

freshness_policies:
  volatile:
    refresh_after_seconds: 300
    expire_after_seconds: 900

facts:
  - id: inventory_snapshot
    observed_at: "2026-09-11T09:00:00Z"
    freshness_policy: volatile
    provenance:
      source: amazon-sp-api
      reference: inventory-summaries
    refresh:
      adapter: inventory-api
      reference: inventory:SKU-1

nodes:
  - id: reorder_recommendation
    depends_on:
      facts: [inventory_snapshot]

  - id: purchase_order
    depends_on:
      nodes: [reorder_recommendation]
```

Hard freshness bounds:

- `ttl_seconds`: validity duration from `observed_at`;
- `valid_until`: explicit absolute expiry;
- `freshness_policy.expire_after_seconds`: reusable hard expiry;
- when several hard bounds apply, FreshPlan uses the earliest.

Soft freshness boundary:

- `freshness_policy.refresh_after_seconds`: marks the fact `refresh_due` before hard expiry.

All timestamps must be timezone-aware. `refresh.adapter` is a logical adapter name; `refresh.reference` is an opaque locator passed to trusted application code.

## Freshness semantics

A fact can be:

- `fresh`: before the soft refresh boundary and hard expiry;
- `refresh_due`: soft refresh boundary reached but evidence is still valid;
- `stale`: hard expiry reached, or `observed_at` is in the future relative to the evaluation clock.

`refresh_due` recommends evidence renewal but does not invalidate the plan. Only stale facts invalidate dependent plan nodes. FreshPlan propagates root stale-fact IDs through the affected branch and emits a topological `replan_order`; unrelated plan nodes remain valid.

Cycles, self-dependencies, unknown fact/node references, invalid policy references, and policy windows where `refresh_after_seconds > expire_after_seconds` are rejected.

## Refresh requests

```bash
trustforge freshplan requests \
  --plan examples/freshplan/refreshable-order.yaml \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

Refresh requests are generated for both `refresh_due` and `stale` facts. A request includes only fact id, configured adapter, opaque reference, status/reason, timestamps, policy metadata, and provenance. Raw fact values are not copied into refresh requests.

## Replacement evidence

Replacement evidence is metadata-only and must include an explicit change classification:

```json
{
  "version": "0.1",
  "replacements": [
    {
      "fact_id": "inventory_snapshot",
      "evidence_id": "sp-api:inventory:20260911T0929Z",
      "observed_at": "2026-09-11T09:29:00Z",
      "provenance": {
        "source": "amazon-sp-api",
        "reference": "inventory-summaries:refresh-2"
      },
      "change": "changed"
    }
  ]
}
```

Allowed change values:

- `changed`: replacement meaningfully differs, so affected nodes must be re-planned;
- `unchanged`: replacement confirms the previous fact still holds; affected nodes may resume once freshness is restored;
- `unknown`: change cannot be established, so FreshPlan conservatively treats it like `changed`.

A replacement may provide new `ttl_seconds` / `valid_until`. If both are omitted, existing fact hard bounds or the named freshness policy are preserved. Raw `value` fields and unknown replacement fields are rejected.

## Plan patch

```bash
trustforge freshplan patch \
  --plan examples/freshplan/refreshable-order.yaml \
  --evidence examples/freshplan/replacement-evidence.json \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

Patch operations are deliberately small:

- `blocked`: replacement evidence is still stale, so the node must not continue;
- `replan`: replacement changed or is unknown;
- `resume`: freshness was restored and replacement is explicitly unchanged.

Blocked operations take precedence over re-plan operations. Operations are emitted in dependency-safe topological order. Nodes outside the affected branch remain in `unaffected_nodes`.

Use `--fail-on-replan` to exit `6` when the patch is blocked or requires re-planning.

## Trusted adapter API

Application code may register trusted adapters explicitly:

```python
from trustforge.freshplan_refresh import CallableRefreshAdapter, refresh_with_adapters

adapter = CallableRefreshAdapter("inventory-api", refresh_inventory)
patch = refresh_with_adapters(
    plan,
    {"inventory-api": adapter},
    as_of="2026-09-11T09:30:00Z",
)
```

FreshPlan intentionally does not support CLI dynamic imports of adapter modules. Adapter exceptions, missing registrations, malformed replacement evidence, and evidence returned for the wrong fact fail closed as `FreshPlanRefreshError`.

## Performance benchmark

```bash
trustforge freshplan benchmark \
  --nodes 1000 5000 10000 \
  --repeats 3 \
  --json
```

The deterministic `parallel-chains-v1` generator reports nodes, facts, edges, median/min/max evaluation time, throughput, stale facts, and invalidated nodes. CI runs a 10k-node case with a deliberately loose 5-second median threshold as a regression alarm, not as a universal performance guarantee.

## Core CLI

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

For CI or orchestration gates:

```bash
trustforge freshplan check --plan plan.yaml --fail-on-stale
```

Exit codes:

- `0`: document/operation is valid and no requested gate failed;
- `6`: invalid FreshPlan input, refresh failure, file error, stale/replan gate failure, or performance gate failure.

## Contracts

- `contracts/freshplan.schema.json` — plan metadata, policies and graph;
- `contracts/freshplan-refresh-request.schema.json` — value-free refresh request report;
- `contracts/freshplan-replacement.schema.json` — strict replacement evidence;
- `contracts/freshplan-patch.schema.json` — minimal control-plane patch.

## Boundaries

FreshPlan does not ship network-specific refresh implementations. The adapter interface is transport-agnostic trusted application code.

FreshPlan does not prove that a freshness policy is appropriate for a domain, does not compare raw domain values itself, and does not mutate the caller's external fact store. The replacement `change` classification must come from the source adapter or surrounding application logic.

`unknown` is intentionally conservative: inability to establish equivalence is not treated as permission to resume stale reasoning. The benchmark is synthetic and should be used as a regression signal, not as a production capacity guarantee.

## Next work

- async refresh adapters;
- runtime integrations for long-running agent frameworks;
- persistent state-store adapters for replacement metadata;
- broader graph-shape benchmarks;
- domain-specific policy profiles and policy linting;
- v0.5.0 release hardening.
