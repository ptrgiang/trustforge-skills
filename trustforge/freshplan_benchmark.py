from __future__ import annotations

import json
import statistics
import time
from typing import Any, Iterable

from .freshplan import evaluate


class FreshPlanBenchmarkError(ValueError):
    """Raised when FreshPlan benchmark configuration is invalid."""


AS_OF = "2026-09-11T09:30:00Z"


def generate_plan(node_count: int) -> dict[str, Any]:
    if isinstance(node_count, bool) or not isinstance(node_count, int) or node_count <= 0:
        raise FreshPlanBenchmarkError("node_count must be a positive integer")

    fact_count = max(10, min(1000, max(1, node_count // 10)))
    facts: list[dict[str, Any]] = []
    for index in range(fact_count):
        stale = index % 10 == 0
        facts.append(
            {
                "id": f"fact-{index:05d}",
                "observed_at": (
                    "2026-09-11T08:00:00Z" if stale else "2026-09-11T09:20:00Z"
                ),
                "freshness_policy": "benchmark",
                "provenance": {
                    "source": "synthetic-benchmark",
                    "reference": f"fact:{index}",
                },
            }
        )

    nodes: list[dict[str, Any]] = []
    for index in range(node_count):
        depends_on: dict[str, list[str]] = {
            "facts": [f"fact-{index % fact_count:05d}"]
        }
        if index >= fact_count:
            depends_on["nodes"] = [f"node-{index - fact_count:06d}"]
        nodes.append(
            {
                "id": f"node-{index:06d}",
                "depends_on": depends_on,
            }
        )

    return {
        "version": "0.1",
        "plan_id": f"benchmark-{node_count}",
        "freshness_policies": {
            "benchmark": {
                "refresh_after_seconds": 900,
                "expire_after_seconds": 1800,
            }
        },
        "facts": facts,
        "nodes": nodes,
    }


def benchmark(
    node_counts: Iterable[int],
    *,
    repeats: int = 3,
) -> dict[str, Any]:
    sizes = list(node_counts)
    if not sizes:
        raise FreshPlanBenchmarkError("at least one node count is required")
    if any(isinstance(size, bool) or not isinstance(size, int) or size <= 0 for size in sizes):
        raise FreshPlanBenchmarkError("node counts must be positive integers")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats <= 0:
        raise FreshPlanBenchmarkError("repeats must be a positive integer")

    cases: list[dict[str, Any]] = []
    for size in sizes:
        plan = generate_plan(size)
        timings_ms: list[float] = []
        last_report: dict[str, Any] | None = None

        for _ in range(repeats):
            started = time.perf_counter()
            last_report = evaluate(plan, as_of=AS_OF)
            timings_ms.append((time.perf_counter() - started) * 1000.0)

        assert last_report is not None
        median_ms = statistics.median(timings_ms)
        fact_count = len(plan["facts"])
        edge_count = size + max(size - fact_count, 0)
        cases.append(
            {
                "nodes": size,
                "facts": fact_count,
                "edges": edge_count,
                "repeats": repeats,
                "median_ms": round(median_ms, 3),
                "min_ms": round(min(timings_ms), 3),
                "max_ms": round(max(timings_ms), 3),
                "nodes_per_second": (
                    round((size / median_ms) * 1000.0, 1) if median_ms > 0 else None
                ),
                "stale_facts": last_report["summary"]["stale_facts"],
                "invalidated_nodes": last_report["summary"]["invalidated_nodes"],
            }
        )

    largest = max(cases, key=lambda item: item["nodes"])
    return {
        "schema_version": "0.1",
        "as_of": AS_OF,
        "generator": "parallel-chains-v1",
        "cases": cases,
        "largest_case": largest,
    }


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "FreshPlan performance benchmark",
        f"generator: {report['generator']}",
        f"as_of: {report['as_of']}",
    ]
    for case in report["cases"]:
        lines.append(
            f"- {case['nodes']} nodes / {case['edges']} edges: "
            f"median={case['median_ms']:.3f}ms "
            f"throughput={case['nodes_per_second']} nodes/s "
            f"invalidated={case['invalidated_nodes']}"
        )
    return "\n".join(lines)
