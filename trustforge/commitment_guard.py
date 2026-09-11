from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _get_nested(mapping: dict[str, Any], dotted_key: str) -> tuple[bool, Any]:
    value: Any = mapping
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def _check(actual: Any, rule: dict[str, Any]) -> tuple[str, str]:
    if "equals" in rule:
        expected = rule["equals"]
        return ("PASS", f"equals {expected!r}") if actual == expected else ("FAIL", f"expected {expected!r}, got {actual!r}")
    if "gte" in rule:
        expected = rule["gte"]
        try:
            ok = actual >= expected
        except TypeError:
            ok = False
        return ("PASS", f">= {expected!r}") if ok else ("FAIL", f"expected >= {expected!r}, got {actual!r}")
    if "lte" in rule:
        expected = rule["lte"]
        try:
            ok = actual <= expected
        except TypeError:
            ok = False
        return ("PASS", f"<= {expected!r}") if ok else ("FAIL", f"expected <= {expected!r}, got {actual!r}")
    if rule.get("truthy") is True:
        return ("PASS", "truthy") if bool(actual) else ("FAIL", f"expected truthy, got {actual!r}")
    if "contains" in rule:
        expected = rule["contains"]
        try:
            ok = expected in actual
        except TypeError:
            ok = False
        return ("PASS", f"contains {expected!r}") if ok else ("FAIL", f"expected value containing {expected!r}, got {actual!r}")
    return "UNKNOWN", "unsupported check operator"


def verify(contract: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    commitments = contract.get("commitments")
    if not isinstance(commitments, list):
        raise ValueError("contract.commitments must be a list")

    results: list[dict[str, Any]] = []
    for item in commitments:
        cid = str(item.get("id", "UNNAMED"))
        description = str(item.get("description", ""))
        waiver = item.get("waiver")
        if waiver:
            results.append({
                "id": cid,
                "description": description,
                "status": "WAIVED",
                "detail": str(waiver),
            })
            continue

        rule = item.get("evidence")
        if not isinstance(rule, dict) or "key" not in rule:
            results.append({
                "id": cid,
                "description": description,
                "status": "UNKNOWN",
                "detail": "missing evidence rule",
            })
            continue

        key = str(rule["key"])
        found, actual = _get_nested(evidence, key)
        if not found:
            results.append({
                "id": cid,
                "description": description,
                "status": "UNKNOWN",
                "detail": f"evidence key not found: {key}",
            })
            continue

        status, detail = _check(actual, rule)
        results.append({
            "id": cid,
            "description": description,
            "status": status,
            "detail": detail,
            "actual": actual,
        })

    blocking = [result for result in results if result["status"] in {"FAIL", "UNKNOWN"}]
    return {
        "verified_complete": not blocking,
        "summary": {
            "pass": sum(r["status"] == "PASS" for r in results),
            "fail": sum(r["status"] == "FAIL" for r in results),
            "unknown": sum(r["status"] == "UNKNOWN" for r in results),
            "waived": sum(r["status"] == "WAIVED" for r in results),
        },
        "commitments": results,
    }


def verify_files(contract_path: str | Path, evidence_path: str | Path) -> dict[str, Any]:
    return verify(_load_json(contract_path), _load_json(evidence_path))


def render_text(report: dict[str, Any]) -> str:
    lines = ["TrustForge CommitmentGuard", "==========================", ""]
    for item in report["commitments"]:
        lines.append(f"{item['id']} {item['status']}: {item['description']}")
        lines.append(f"  {item['detail']}")
    lines.extend([
        "",
        "Result: VERIFIED COMPLETE" if report["verified_complete"] else "Result: NOT VERIFIED",
    ])
    return "\n".join(lines)
