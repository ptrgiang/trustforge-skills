from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml


class FreshPlanError(ValueError):
    """Raised when a FreshPlan document is invalid."""


def _parse_timestamp(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise FreshPlanError(f"{field} must include a timezone offset")
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise FreshPlanError(f"{field} must be a non-empty ISO-8601 timestamp")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise FreshPlanError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FreshPlanError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreshPlanError(f"{field} must be a non-empty string")
    return value.strip()


def load_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    text = plan_path.read_text(encoding="utf-8")
    suffix = plan_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise FreshPlanError("FreshPlan document must be a mapping/object")
    return data


def _fact_expiry(fact: dict[str, Any], fact_id: str, observed_at: datetime) -> datetime:
    candidates: list[datetime] = []

    ttl = fact.get("ttl_seconds")
    if ttl is not None:
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl < 0:
            raise FreshPlanError(f"fact {fact_id}: ttl_seconds must be a non-negative number")
        candidates.append(observed_at + timedelta(seconds=float(ttl)))

    valid_until = fact.get("valid_until")
    if valid_until is not None:
        candidates.append(_parse_timestamp(valid_until, f"fact {fact_id}.valid_until"))

    if not candidates:
        raise FreshPlanError(
            f"fact {fact_id}: at least one freshness bound is required "
            "(ttl_seconds or valid_until)"
        )
    return min(candidates)


def _normalize_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FreshPlanError(f"{field} must be an array")
    return [_require_id(item, field) for item in value]


def _validate_and_index(plan: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if str(plan.get("version")) != "0.1":
        raise FreshPlanError("FreshPlan version must be '0.1'")

    raw_facts = plan.get("facts", [])
    raw_nodes = plan.get("nodes", [])
    if not isinstance(raw_facts, list) or not isinstance(raw_nodes, list):
        raise FreshPlanError("facts and nodes must be arrays")

    facts: dict[str, dict[str, Any]] = {}
    for idx, fact in enumerate(raw_facts):
        if not isinstance(fact, dict):
            raise FreshPlanError(f"facts[{idx}] must be an object")
        fact_id = _require_id(fact.get("id"), f"facts[{idx}].id")
        if fact_id in facts:
            raise FreshPlanError(f"duplicate fact id: {fact_id}")
        provenance = fact.get("provenance")
        if not isinstance(provenance, dict):
            raise FreshPlanError(f"fact {fact_id}: provenance must be an object")
        _require_id(provenance.get("source"), f"fact {fact_id}.provenance.source")
        facts[fact_id] = fact

    nodes: dict[str, dict[str, Any]] = {}
    for idx, node in enumerate(raw_nodes):
        if not isinstance(node, dict):
            raise FreshPlanError(f"nodes[{idx}] must be an object")
        node_id = _require_id(node.get("id"), f"nodes[{idx}].id")
        if node_id in nodes:
            raise FreshPlanError(f"duplicate node id: {node_id}")
        depends = node.get("depends_on", {})
        if depends is None:
            depends = {}
        if not isinstance(depends, dict):
            raise FreshPlanError(f"node {node_id}: depends_on must be an object")
        fact_deps = _normalize_list(depends.get("facts"), f"node {node_id}.depends_on.facts")
        node_deps = _normalize_list(depends.get("nodes"), f"node {node_id}.depends_on.nodes")
        nodes[node_id] = {**node, "_fact_deps": fact_deps, "_node_deps": node_deps}

    for node_id, node in nodes.items():
        unknown_facts = sorted(set(node["_fact_deps"]) - facts.keys())
        unknown_nodes = sorted(set(node["_node_deps"]) - nodes.keys())
        if unknown_facts:
            raise FreshPlanError(f"node {node_id}: unknown fact dependencies: {', '.join(unknown_facts)}")
        if unknown_nodes:
            raise FreshPlanError(f"node {node_id}: unknown node dependencies: {', '.join(unknown_nodes)}")
        if node_id in node["_node_deps"]:
            raise FreshPlanError(f"node {node_id}: self dependency is not allowed")

    return facts, nodes


def _topological_order(nodes: dict[str, dict[str, Any]]) -> list[str]:
    indegree = {node_id: len(set(node["_node_deps"])) for node_id, node in nodes.items()}
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for node_id, node in nodes.items():
        for dep in set(node["_node_deps"]):
            children[dep].append(node_id)

    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for child in sorted(children[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()

    if len(order) != len(nodes):
        cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
        raise FreshPlanError(f"plan node dependency cycle detected: {', '.join(cyclic)}")
    return order


def evaluate(plan: dict[str, Any], *, as_of: str | datetime | None = None) -> dict[str, Any]:
    facts, nodes = _validate_and_index(plan)
    topo = _topological_order(nodes)

    if as_of is None:
        now = datetime.now(timezone.utc)
    elif isinstance(as_of, datetime):
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise FreshPlanError("as_of datetime must include timezone information")
        now = as_of.astimezone(timezone.utc)
    else:
        now = _parse_timestamp(as_of, "as_of")

    fact_reports: list[dict[str, Any]] = []
    stale_facts: set[str] = set()

    for fact_id in sorted(facts):
        fact = facts[fact_id]
        observed = _parse_timestamp(fact.get("observed_at"), f"fact {fact_id}.observed_at")
        expires = _fact_expiry(fact, fact_id, observed)

        if observed > now:
            status = "stale"
            reason = "observed_at_in_future"
            age_seconds = (now - observed).total_seconds()
        elif now >= expires:
            status = "stale"
            reason = "expired"
            age_seconds = (now - observed).total_seconds()
        else:
            status = "fresh"
            reason = "within_validity_window"
            age_seconds = (now - observed).total_seconds()

        if status == "stale":
            stale_facts.add(fact_id)

        provenance = fact["provenance"]
        safe_provenance = {"source": provenance["source"]}
        for key in ("reference", "observed_by"):
            if key in provenance:
                safe_provenance[key] = provenance[key]

        fact_reports.append(
            {
                "id": fact_id,
                "status": status,
                "reason": reason,
                "observed_at": _iso(observed),
                "expires_at": _iso(expires),
                "age_seconds": round(age_seconds, 3),
                "provenance": safe_provenance,
            }
        )

    invalidated: dict[str, dict[str, Any]] = {}
    for node_id in topo:
        node = nodes[node_id]
        direct = sorted(set(node["_fact_deps"]) & stale_facts)
        invalidated_deps = sorted(dep for dep in node["_node_deps"] if dep in invalidated)
        if not direct and not invalidated_deps:
            continue

        root_stale = set(direct)
        parent_depths: list[int] = []
        for dep in invalidated_deps:
            root_stale.update(invalidated[dep]["root_stale_facts"])
            parent_depths.append(int(invalidated[dep]["depth"]))

        depth = 0 if direct else (max(parent_depths) + 1 if parent_depths else 0)
        if direct and parent_depths:
            depth = max([0, *(d + 1 for d in parent_depths)])

        invalidated[node_id] = {
            "id": node_id,
            "direct_stale_facts": direct,
            "invalidated_dependencies": invalidated_deps,
            "root_stale_facts": sorted(root_stale),
            "depth": depth,
        }

    replan_order = [node_id for node_id in topo if node_id in invalidated]
    unaffected = [node_id for node_id in topo if node_id not in invalidated]

    return {
        "schema_version": "0.1",
        "as_of": _iso(now),
        "decision": "replan_required" if invalidated else "fresh",
        "summary": {
            "facts_total": len(facts),
            "stale_facts": len(stale_facts),
            "nodes_total": len(nodes),
            "invalidated_nodes": len(invalidated),
            "unaffected_nodes": len(unaffected),
        },
        "facts": fact_reports,
        "stale_facts": sorted(stale_facts),
        "invalidated_nodes": [invalidated[node_id] for node_id in replan_order],
        "replan_order": replan_order,
        "unaffected_nodes": unaffected,
    }


def evaluate_file(path: str | Path, *, as_of: str | datetime | None = None) -> dict[str, Any]:
    return evaluate(load_plan(path), as_of=as_of)


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "FreshPlan freshness check",
        f"as_of: {report['as_of']}",
        f"decision: {report['decision']}",
        f"stale facts: {report['summary']['stale_facts']} / {report['summary']['facts_total']}",
        f"invalidated nodes: {report['summary']['invalidated_nodes']} / {report['summary']['nodes_total']}",
    ]
    if report["stale_facts"]:
        lines.append("stale_fact_ids: " + ", ".join(report["stale_facts"]))
    if report["replan_order"]:
        lines.append("replan_order: " + " -> ".join(report["replan_order"]))
        for node in report["invalidated_nodes"]:
            roots = ", ".join(node["root_stale_facts"]) or "-"
            lines.append(f"- {node['id']}: root stale facts = {roots}")
    else:
        lines.append("replan_order: none")
    return "\n".join(lines)
