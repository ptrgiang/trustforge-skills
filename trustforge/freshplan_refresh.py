from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import yaml

from .freshplan import FreshPlanError, evaluate, load_plan


class FreshPlanRefreshError(FreshPlanError):
    """Raised when FreshPlan refresh evidence or adapter execution is invalid."""


class FactRefreshAdapter(Protocol):
    name: str

    def refresh(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return replacement evidence for one fact."""


@dataclass
class CallableRefreshAdapter:
    name: str
    fn: Callable[[dict[str, Any]], dict[str, Any]]

    def refresh(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.fn(request)


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreshPlanRefreshError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_timestamp(value: str, field: str) -> str:
    raw = _require_text(value, field)
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise FreshPlanRefreshError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FreshPlanRefreshError(f"{field} must include a timezone offset")
    return raw


def _safe_provenance(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise FreshPlanRefreshError(f"{field} must be an object")
    source = _require_text(value.get("source"), f"{field}.source")
    result = {"source": source}
    for key in ("reference", "observed_by"):
        if key in value:
            if not isinstance(value[key], str):
                raise FreshPlanRefreshError(f"{field}.{key} must be a string")
            result[key] = value[key]
    return result


def _fact_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts = plan.get("facts", [])
    if not isinstance(facts, list):
        raise FreshPlanRefreshError("facts must be an array")
    result: dict[str, dict[str, Any]] = {}
    for idx, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise FreshPlanRefreshError(f"facts[{idx}] must be an object")
        fact_id = _require_text(fact.get("id"), f"facts[{idx}].id")
        result[fact_id] = fact
    return result


def _node_graph(plan: dict[str, Any]) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    nodes = plan.get("nodes", [])
    if not isinstance(nodes, list):
        raise FreshPlanRefreshError("nodes must be an array")

    node_deps: dict[str, set[str]] = {}
    fact_deps: dict[str, set[str]] = {}
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise FreshPlanRefreshError(f"nodes[{idx}] must be an object")
        node_id = _require_text(node.get("id"), f"nodes[{idx}].id")
        depends = node.get("depends_on") or {}
        if not isinstance(depends, dict):
            raise FreshPlanRefreshError(f"node {node_id}.depends_on must be an object")
        raw_nodes = depends.get("nodes") or []
        raw_facts = depends.get("facts") or []
        if not isinstance(raw_nodes, list) or not isinstance(raw_facts, list):
            raise FreshPlanRefreshError(f"node {node_id} dependencies must be arrays")
        node_deps[node_id] = {_require_text(v, f"node {node_id}.depends_on.nodes") for v in raw_nodes}
        fact_deps[node_id] = {_require_text(v, f"node {node_id}.depends_on.facts") for v in raw_facts}

    indegree = {node_id: len(deps) for node_id, deps in node_deps.items()}
    children = {node_id: set() for node_id in node_deps}
    for node_id, deps in node_deps.items():
        for dep in deps:
            if dep not in children:
                raise FreshPlanRefreshError(f"node {node_id}: unknown node dependency: {dep}")
            children[dep].add(node_id)
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    topo: list[str] = []
    while ready:
        node_id = ready.pop(0)
        topo.append(node_id)
        for child in sorted(children[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(topo) != len(node_deps):
        raise FreshPlanRefreshError("plan node dependency cycle detected")
    return topo, fact_deps, children


def build_refresh_requests(plan: dict[str, Any], *, as_of: str | None = None) -> dict[str, Any]:
    report = evaluate(plan, as_of=as_of)
    facts = _fact_map(plan)
    reports = {item["id"]: item for item in report["facts"]}
    requests: list[dict[str, Any]] = []

    for fact_id in report["stale_facts"]:
        fact = facts[fact_id]
        refresh = fact.get("refresh")
        configured = isinstance(refresh, dict) and isinstance(refresh.get("adapter"), str) and bool(refresh["adapter"].strip())
        adapter = refresh["adapter"].strip() if configured else None
        reference = None
        if isinstance(refresh, dict) and isinstance(refresh.get("reference"), str):
            reference = refresh["reference"]
        elif isinstance(fact.get("provenance"), dict) and isinstance(fact["provenance"].get("reference"), str):
            reference = fact["provenance"]["reference"]

        item = reports[fact_id]
        requests.append(
            {
                "fact_id": fact_id,
                "configured": configured,
                "adapter": adapter,
                "reference": reference,
                "reason": item["reason"],
                "as_of": report["as_of"],
                "current": {
                    "observed_at": item["observed_at"],
                    "expires_at": item["expires_at"],
                    "provenance": item["provenance"],
                },
            }
        )

    return {
        "schema_version": "0.1",
        "as_of": report["as_of"],
        "decision": "refresh_required" if requests else "fresh",
        "summary": {
            "stale_facts": len(requests),
            "configured_requests": sum(1 for item in requests if item["configured"]),
            "unconfigured_requests": sum(1 for item in requests if not item["configured"]),
        },
        "requests": requests,
    }


def build_refresh_requests_file(path: str | Path, *, as_of: str | None = None) -> dict[str, Any]:
    return build_refresh_requests(load_plan(path), as_of=as_of)


_ALLOWED_REPLACEMENT_KEYS = {
    "fact_id",
    "evidence_id",
    "observed_at",
    "ttl_seconds",
    "valid_until",
    "provenance",
    "change",
}


def _normalize_replacement(item: Any, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise FreshPlanRefreshError(f"replacements[{index}] must be an object")
    unknown = sorted(set(item) - _ALLOWED_REPLACEMENT_KEYS)
    if unknown:
        raise FreshPlanRefreshError(
            f"replacements[{index}] contains unsupported fields: {', '.join(unknown)}"
        )
    fact_id = _require_text(item.get("fact_id"), f"replacements[{index}].fact_id")
    evidence_id = _require_text(item.get("evidence_id"), f"replacement {fact_id}.evidence_id")
    observed_at = _validate_timestamp(item.get("observed_at"), f"replacement {fact_id}.observed_at")
    change = _require_text(item.get("change"), f"replacement {fact_id}.change")
    if change not in {"changed", "unchanged", "unknown"}:
        raise FreshPlanRefreshError(
            f"replacement {fact_id}.change must be changed, unchanged, or unknown"
        )
    has_ttl = "ttl_seconds" in item
    has_until = "valid_until" in item
    if not has_ttl and not has_until:
        raise FreshPlanRefreshError(
            f"replacement {fact_id} requires ttl_seconds or valid_until"
        )
    result: dict[str, Any] = {
        "fact_id": fact_id,
        "evidence_id": evidence_id,
        "observed_at": observed_at,
        "provenance": _safe_provenance(item.get("provenance"), f"replacement {fact_id}.provenance"),
        "change": change,
    }
    if has_ttl:
        ttl = item["ttl_seconds"]
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl < 0:
            raise FreshPlanRefreshError(f"replacement {fact_id}.ttl_seconds must be non-negative")
        result["ttl_seconds"] = ttl
    if has_until:
        result["valid_until"] = _validate_timestamp(
            item["valid_until"], f"replacement {fact_id}.valid_until"
        )
    return result


def normalize_replacement_evidence(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise FreshPlanRefreshError("replacement evidence must be an object")
    if str(document.get("version")) != "0.1":
        raise FreshPlanRefreshError("replacement evidence version must be '0.1'")
    raw = document.get("replacements")
    if not isinstance(raw, list):
        raise FreshPlanRefreshError("replacement evidence replacements must be an array")
    replacements = [_normalize_replacement(item, idx) for idx, item in enumerate(raw)]
    ids = [item["fact_id"] for item in replacements]
    duplicates = sorted({fact_id for fact_id in ids if ids.count(fact_id) > 1})
    if duplicates:
        raise FreshPlanRefreshError(f"duplicate replacement fact ids: {', '.join(duplicates)}")
    return {"version": "0.1", "replacements": replacements}


def load_replacement_evidence(path: str | Path) -> dict[str, Any]:
    evidence_path = Path(path)
    text = evidence_path.read_text(encoding="utf-8")
    suffix = evidence_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = yaml.safe_load(text)
    return normalize_replacement_evidence(data)


def apply_replacements(
    plan: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = normalize_replacement_evidence(evidence)
    updated = copy.deepcopy(plan)
    facts = _fact_map(updated)
    applied: list[dict[str, Any]] = []

    for replacement in normalized["replacements"]:
        fact_id = replacement["fact_id"]
        if fact_id not in facts:
            raise FreshPlanRefreshError(f"replacement references unknown fact: {fact_id}")
        fact = facts[fact_id]
        fact["observed_at"] = replacement["observed_at"]
        fact["provenance"] = copy.deepcopy(replacement["provenance"])
        fact.pop("ttl_seconds", None)
        fact.pop("valid_until", None)
        if "ttl_seconds" in replacement:
            fact["ttl_seconds"] = replacement["ttl_seconds"]
        if "valid_until" in replacement:
            fact["valid_until"] = replacement["valid_until"]
        applied.append(copy.deepcopy(replacement))

    return updated, applied


def _affected_by_facts(
    facts: set[str],
    topo: list[str],
    fact_deps: dict[str, set[str]],
    children: dict[str, set[str]],
) -> dict[str, set[str]]:
    roots: dict[str, set[str]] = {}
    for node_id in topo:
        direct = fact_deps[node_id] & facts
        inherited: set[str] = set()
        for parent, parent_children in children.items():
            if node_id in parent_children and parent in roots:
                inherited.update(roots[parent])
        combined = direct | inherited
        if combined:
            roots[node_id] = combined
    return roots


def build_plan_patch(
    plan: dict[str, Any],
    evidence: dict[str, Any],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    before = evaluate(plan, as_of=as_of)
    updated_plan, replacements = apply_replacements(plan, evidence)
    after = evaluate(updated_plan, as_of=before["as_of"])

    topo, fact_deps, children = _node_graph(plan)
    before_invalidated = {item["id"]: item for item in before["invalidated_nodes"]}
    after_invalidated = {item["id"]: item for item in after["invalidated_nodes"]}

    conservative_facts = {
        item["fact_id"] for item in replacements if item["change"] in {"changed", "unknown"}
    }
    conservative_roots = _affected_by_facts(conservative_facts, topo, fact_deps, children)

    blocked = set(after_invalidated)
    replan = set(conservative_roots) - blocked
    resume = set(before_invalidated) - blocked - replan

    operations: list[dict[str, Any]] = []
    for node_id in topo:
        if node_id in blocked:
            roots = after_invalidated[node_id]["root_stale_facts"]
            operations.append(
                {
                    "op": "blocked",
                    "node_id": node_id,
                    "root_facts": roots,
                    "reason": "freshness_not_restored",
                }
            )
        elif node_id in replan:
            roots = sorted(conservative_roots[node_id])
            operations.append(
                {
                    "op": "replan",
                    "node_id": node_id,
                    "root_facts": roots,
                    "reason": "replacement_changed_or_unknown",
                }
            )
        elif node_id in resume:
            prior_roots = set(before_invalidated[node_id]["root_stale_facts"])
            recovered = sorted(prior_roots - set(after["stale_facts"]))
            operations.append(
                {
                    "op": "resume",
                    "node_id": node_id,
                    "root_facts": recovered,
                    "reason": "freshness_restored_without_change",
                }
            )

    if blocked:
        decision = "blocked"
    elif replan:
        decision = "replan_required"
    elif resume:
        decision = "resumable"
    else:
        decision = "no_change"

    op_nodes = {item["node_id"] for item in operations}
    replacement_summary = [
        {
            "fact_id": item["fact_id"],
            "evidence_id": item["evidence_id"],
            "change": item["change"],
            "observed_at": item["observed_at"],
            "provenance": item["provenance"],
        }
        for item in replacements
    ]
    return {
        "schema_version": "0.1",
        "as_of": after["as_of"],
        "decision": decision,
        "summary": {
            "replacements": len(replacements),
            "blocked_nodes": len(blocked),
            "replan_nodes": len(replan),
            "resume_nodes": len(resume),
            "unaffected_nodes": len(topo) - len(op_nodes),
        },
        "replacements": replacement_summary,
        "before": {
            "stale_facts": before["stale_facts"],
            "invalidated_nodes": [item["id"] for item in before["invalidated_nodes"]],
        },
        "after": {
            "stale_facts": after["stale_facts"],
            "invalidated_nodes": [item["id"] for item in after["invalidated_nodes"]],
        },
        "operations": operations,
        "blocked_nodes": [node_id for node_id in topo if node_id in blocked],
        "replan_order": [node_id for node_id in topo if node_id in replan],
        "resume_nodes": [node_id for node_id in topo if node_id in resume],
        "unaffected_nodes": [node_id for node_id in topo if node_id not in op_nodes],
    }


def build_plan_patch_file(
    plan_path: str | Path,
    evidence_path: str | Path,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    return build_plan_patch(
        load_plan(plan_path),
        load_replacement_evidence(evidence_path),
        as_of=as_of,
    )


def run_refresh_adapters(
    plan: dict[str, Any],
    adapters: Mapping[str, FactRefreshAdapter],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    request_report = build_refresh_requests(plan, as_of=as_of)
    replacements: list[dict[str, Any]] = []
    for request in request_report["requests"]:
        if not request["configured"]:
            raise FreshPlanRefreshError(
                f"fact {request['fact_id']} is stale but has no refresh adapter configured"
            )
        adapter_name = request["adapter"]
        adapter = adapters.get(adapter_name)
        if adapter is None:
            raise FreshPlanRefreshError(
                f"no refresh adapter registered for {adapter_name!r} "
                f"(fact {request['fact_id']})"
            )
        try:
            raw = adapter.refresh(copy.deepcopy(request))
        except Exception as exc:
            raise FreshPlanRefreshError(
                f"refresh adapter {adapter_name!r} failed for fact {request['fact_id']}"
            ) from exc
        replacement = _normalize_replacement(raw, len(replacements))
        if replacement["fact_id"] != request["fact_id"]:
            raise FreshPlanRefreshError(
                f"refresh adapter {adapter_name!r} returned evidence for "
                f"{replacement['fact_id']!r}, expected {request['fact_id']!r}"
            )
        replacements.append(replacement)
    return {"version": "0.1", "replacements": replacements}


def refresh_with_adapters(
    plan: dict[str, Any],
    adapters: Mapping[str, FactRefreshAdapter],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    evidence = run_refresh_adapters(plan, adapters, as_of=as_of)
    return build_plan_patch(plan, evidence, as_of=as_of)


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_requests_text(report: dict[str, Any]) -> str:
    lines = [
        "FreshPlan refresh requests",
        f"as_of: {report['as_of']}",
        f"decision: {report['decision']}",
        f"stale facts: {report['summary']['stale_facts']}",
    ]
    for item in report["requests"]:
        adapter = item["adapter"] or "UNCONFIGURED"
        lines.append(f"- {item['fact_id']}: adapter={adapter} reason={item['reason']}")
    return "\n".join(lines)


def render_patch_text(report: dict[str, Any]) -> str:
    lines = [
        "FreshPlan plan patch",
        f"as_of: {report['as_of']}",
        f"decision: {report['decision']}",
        (
            "operations: "
            f"blocked={report['summary']['blocked_nodes']} "
            f"replan={report['summary']['replan_nodes']} "
            f"resume={report['summary']['resume_nodes']}"
        ),
    ]
    for item in report["operations"]:
        roots = ", ".join(item["root_facts"]) or "-"
        lines.append(f"- {item['op']} {item['node_id']}: root facts = {roots}")
    if not report["operations"]:
        lines.append("- no node operations")
    return "\n".join(lines)
