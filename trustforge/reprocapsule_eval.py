from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reprocapsule import sanitize_trace


class ReproCapsuleBenchmarkError(ValueError):
    """Raised when a ReproCapsule benchmark dataset is malformed."""


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    cases: list[dict[str, Any]] = []
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReproCapsuleBenchmarkError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ReproCapsuleBenchmarkError(f"line {line_number} must be an object")
        cases.append(item)
    if not cases:
        raise ReproCapsuleBenchmarkError("benchmark dataset is empty")
    return cases


def _validate_case(item: dict[str, Any], index: int) -> None:
    allowed = {"id", "text", "secret_markers", "preserve_markers"}
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise ReproCapsuleBenchmarkError(f"case {index} has unknown fields: {', '.join(unknown)}")
    if not isinstance(item.get("id"), str) or not item["id"]:
        raise ReproCapsuleBenchmarkError(f"case {index} requires a non-empty id")
    if not isinstance(item.get("text"), str):
        raise ReproCapsuleBenchmarkError(f"case {item['id']} requires text")
    for field in ("secret_markers", "preserve_markers"):
        value = item.get(field, [])
        if not isinstance(value, list) or not all(isinstance(marker, str) and marker for marker in value):
            raise ReproCapsuleBenchmarkError(f"case {item['id']} field {field} must be a list of strings")
    if not item.get("secret_markers") and not item.get("preserve_markers"):
        raise ReproCapsuleBenchmarkError(f"case {item['id']} must declare secret_markers and/or preserve_markers")


def benchmark_file(path: str | Path) -> dict[str, Any]:
    cases = _load_jsonl(path)
    results: list[dict[str, Any]] = []
    positive_total = 0
    positive_passed = 0
    clean_total = 0
    clean_passed = 0

    seen_ids: set[str] = set()
    for index, item in enumerate(cases, start=1):
        _validate_case(item, index)
        case_id = item["id"]
        if case_id in seen_ids:
            raise ReproCapsuleBenchmarkError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)

        text = item["text"]
        secret_markers = item.get("secret_markers", [])
        preserve_markers = item.get("preserve_markers", [])
        sanitized, redactions = sanitize_trace(text)

        secret_ok = all(marker not in sanitized for marker in secret_markers)
        preserve_ok = all(marker in sanitized for marker in preserve_markers)
        unchanged_ok = True
        if preserve_markers and not secret_markers:
            unchanged_ok = sanitized == text

        if secret_markers:
            positive_total += 1
            if secret_ok and preserve_ok:
                positive_passed += 1
        else:
            clean_total += 1
            if preserve_ok and unchanged_ok:
                clean_passed += 1

        results.append(
            {
                "id": case_id,
                "secret_case": bool(secret_markers),
                "secret_markers_removed": secret_ok,
                "preserve_markers_retained": preserve_ok,
                "clean_text_unchanged": unchanged_ok,
                "redactions": redactions,
                "passed": secret_ok and preserve_ok and unchanged_ok,
            }
        )

    secret_recall = positive_passed / positive_total if positive_total else 1.0
    clean_specificity = clean_passed / clean_total if clean_total else 1.0
    return {
        "schema_version": "0.1",
        "dataset": str(Path(path)),
        "cases": len(results),
        "secret_cases": positive_total,
        "clean_cases": clean_total,
        "secret_recall": round(secret_recall, 6),
        "clean_specificity": round(clean_specificity, 6),
        "failed_case_ids": [item["id"] for item in results if not item["passed"]],
        "results": results,
    }


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "ReproCapsule redaction benchmark",
        f"Cases: {report['cases']}",
        f"Secret recall: {report['secret_recall']:.3f}",
        f"Clean specificity: {report['clean_specificity']:.3f}",
    ]
    if report["failed_case_ids"]:
        lines.append("Failed cases: " + ", ".join(report["failed_case_ids"]))
    else:
        lines.append("Failed cases: none")
    return "\n".join(lines)
