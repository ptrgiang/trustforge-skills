---
name: freshplan
description: Detect stale facts in long-running AI-agent plans and selectively invalidate only the dependent plan nodes that must be reconsidered.
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

Turn "this plan was valid when I made it" into an explicit freshness check:

```text
facts + provenance + validity windows
              ↓
        FreshPlan graph
              ↓
        stale fact check
              ↓
 selective dependency invalidation
              ↓
       minimal re-plan set
```

FreshPlan v0.5 evaluates metadata only. It intentionally does not store raw fact values in the FreshPlan contract or report.

## Contract

```yaml
version: "0.1"

facts:
  - id: inventory_snapshot
    observed_at: "2026-09-11T09:00:00Z"
    ttl_seconds: 900
    provenance:
      source: amazon-sp-api
      reference: inventory-summaries

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

All timestamps must be timezone-aware.

## Evaluation semantics

A fact is stale when:

- evaluation time is at or after its expiry; or
- `observed_at` is in the future relative to the evaluation clock, which fails closed as suspicious freshness evidence.

A plan node is invalidated when:

- it directly depends on a stale fact; or
- it depends on another invalidated node.

FreshPlan propagates root stale-fact IDs through the affected branch and emits a topological `replan_order`. Unrelated plan nodes remain valid.

Cycles, self-dependencies, unknown fact references, and unknown node references are rejected.

## CLI

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z"
```

JSON output:

```bash
trustforge freshplan check \
  --plan examples/freshplan/order-fulfillment.yaml \
  --as-of "2026-09-11T09:30:00Z" \
  --json
```

For CI or orchestration gates:

```bash
trustforge freshplan check \
  --plan plan.yaml \
  --fail-on-stale
```

Exit codes:

- `0`: document is valid; with no gate failure;
- `6`: invalid FreshPlan input, file error, or `--fail-on-stale` found an invalidated branch.

## Output

The report contains:

- normalized `as_of`;
- freshness status, expiry, age, and provenance for each fact;
- stale fact IDs;
- invalidated nodes;
- direct stale dependencies;
- invalidated node dependencies;
- root stale facts;
- dependency depth;
- selective `replan_order`;
- unaffected node IDs.

Raw fact values are not copied into the report.

## Boundaries

FreshPlan does not refresh facts itself in v0.5. It determines which facts are stale and which plan nodes must be reconsidered. The runtime or agent remains responsible for fetching replacement evidence and executing the revised plan.

FreshPlan also does not prove that a TTL chosen by the caller is appropriate. Validity windows are policy decisions and should reflect the volatility and risk of each source.

## Next work

- fact refresh adapters;
- explicit plan patch / replacement evidence format;
- graph-size performance benchmarks;
- richer freshness policies beyond TTL and absolute expiry.
