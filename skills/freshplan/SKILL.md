---
name: freshplan
description: Detect stale facts in long-running AI-agent plans, request replacement evidence, and emit minimal control patches for only the affected plan branches.
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
facts + provenance + validity windows
              ↓
        FreshPlan graph
              ↓
        stale fact check
              ↓
     refresh request metadata
              ↓
       replacement evidence
              ↓
  blocked / replan / resume patch
```

FreshPlan reports control metadata rather than raw fact values.

## Fact contract

```yaml
version: "0.1"

facts:
  - id: inventory_snapshot
    observed_at: "2026-09-11T09:00:00Z"
    ttl_seconds: 900
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

Each fact needs provenance plus at least one freshness bound:

- `ttl_seconds`: validity duration from `observed_at`;
- `valid_until`: explicit absolute expiry;
- when both exist, FreshPlan uses the earlier bound.

All timestamps must be timezone-aware. `refresh.adapter` is a logical adapter name; `refresh.reference` is an opaque locator passed to trusted application code.

## Freshness semantics

A fact is stale when:

- evaluation time is at or after its expiry; or
- `observed_at` is in the future relative to the evaluation clock, which fails closed as suspicious freshness evidence.

A plan node is invalidated when it directly depends on a stale fact or depends on another invalidated node. FreshPlan propagates root stale-fact IDs through the affected branch and emits a topological `replan_order`. Unrelated plan nodes remain valid.

Cycles, self-dependencies, unknown fact references, and unknown node references are rejected.

## Refresh requests

```bash
trustforge freshplan requests \
  --plan examples/freshplan/refreshable-order.yaml \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

A refresh request includes only:

- fact id;
- configured adapter name;
- opaque refresh reference;
- stale reason and evaluation time;
- current observed/expiry timestamps and provenance.

Raw fact values are not copied into refresh requests.

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
      "ttl_seconds": 900,
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
- `unknown`: change cannot be established, so FreshPlan conservatively treats it like `changed` and requires re-planning.

Raw `value` fields and unknown replacement fields are rejected.

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
- `6`: invalid FreshPlan input, refresh failure, file error, stale-gate failure, or replan-gate failure.

## Contracts

- `contracts/freshplan.schema.json` — plan metadata and graph;
- `contracts/freshplan-refresh-request.schema.json` — value-free refresh request report;
- `contracts/freshplan-replacement.schema.json` — strict replacement evidence;
- `contracts/freshplan-patch.schema.json` — minimal control-plane patch.

## Boundaries

FreshPlan does not ship network-specific refresh implementations. The adapter interface is transport-agnostic trusted application code.

FreshPlan does not prove that a TTL chosen by the caller is appropriate, does not compare raw domain values itself, and does not mutate the caller's external fact store. The replacement `change` classification must come from the source adapter or surrounding application logic.

`unknown` is intentionally conservative: inability to establish equivalence is not treated as permission to resume stale reasoning.

## Next work

- async refresh adapters;
- large-graph performance benchmarks;
- richer freshness policies beyond TTL and absolute expiry;
- long-running agent framework integrations;
- persistent state-store adapters for replacement metadata.
