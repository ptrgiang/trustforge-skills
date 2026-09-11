from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .datalease import classify_with_plugins
from .datalease_classifiers import FieldClassifier


class DataLeaseBenchmarkError(ValueError):
    """Raised when a benchmark dataset cannot be evaluated."""


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    rows: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DataLeaseBenchmarkError(
                    f"Invalid JSONL at {dataset_path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise DataLeaseBenchmarkError(
                    f"Benchmark row {line_number} must be an object."
                )
            if not isinstance(row.get("id"), str) or not row["id"]:
                raise DataLeaseBenchmarkError(
                    f"Benchmark row {line_number} needs a non-empty string id."
                )
            if not isinstance(row.get("path"), str) or not row["path"]:
                raise DataLeaseBenchmarkError(
                    f"Benchmark row {line_number} needs a non-empty string path."
                )
            expected = row.get("expected", [])
            if not isinstance(expected, list) or not all(
                isinstance(item, str) for item in expected
            ):
                raise DataLeaseBenchmarkError(
                    f"Benchmark row {line_number} expected must be a list of labels."
                )
            rows.append(row)
    if not rows:
        raise DataLeaseBenchmarkError("Benchmark dataset is empty.")
    return rows


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def benchmark_dataset(
    rows: list[dict[str, Any]],
    *,
    classifiers: Iterable[FieldClassifier] | None = None,
) -> dict[str, Any]:
    classifier_plugins = tuple(classifiers or ())
    tp = fp = fn = 0
    exact = 0
    labels_seen: set[str] = set()
    cases: list[dict[str, Any]] = []
    per_label_counts: dict[str, dict[str, int]] = {}

    for row in rows:
        expected = set(row.get("expected", []))
        predicted = {
            finding.label
            for finding in classify_with_plugins(
                row["path"],
                row.get("value"),
                classifier_plugins,
            )
        }
        labels_seen.update(expected)
        labels_seen.update(predicted)

        row_tp = expected & predicted
        row_fp = predicted - expected
        row_fn = expected - predicted
        tp += len(row_tp)
        fp += len(row_fp)
        fn += len(row_fn)
        if expected == predicted:
            exact += 1

        for label in expected | predicted:
            counts = per_label_counts.setdefault(label, {"tp": 0, "fp": 0, "fn": 0})
            if label in expected and label in predicted:
                counts["tp"] += 1
            elif label in predicted:
                counts["fp"] += 1
            else:
                counts["fn"] += 1

        cases.append(
            {
                "id": row["id"],
                "path": row["path"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "false_positive": sorted(row_fp),
                "false_negative": sorted(row_fn),
                "exact": expected == predicted,
            }
        )

    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1 = _safe_ratio(2 * precision * recall, precision + recall) if precision + recall else 0.0

    per_label: dict[str, dict[str, Any]] = {}
    for label in sorted(labels_seen):
        counts = per_label_counts.get(label, {"tp": 0, "fp": 0, "fn": 0})
        label_precision = _safe_ratio(counts["tp"], counts["tp"] + counts["fp"])
        label_recall = _safe_ratio(counts["tp"], counts["tp"] + counts["fn"])
        label_f1 = (
            _safe_ratio(
                2 * label_precision * label_recall,
                label_precision + label_recall,
            )
            if label_precision + label_recall
            else 0.0
        )
        per_label[label] = {
            **counts,
            "precision": round(label_precision, 6),
            "recall": round(label_recall, 6),
            "f1": round(label_f1, 6),
        }

    return {
        "schema_version": "0.1",
        "samples": len(rows),
        "micro": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        },
        "exact_match": {
            "count": exact,
            "rate": round(exact / len(rows), 6),
        },
        "per_label": per_label,
        "cases": cases,
    }


def benchmark_file(
    path: str | Path,
    *,
    classifiers: Iterable[FieldClassifier] | None = None,
) -> dict[str, Any]:
    return benchmark_dataset(load_dataset(path), classifiers=classifiers)


def render_text(report: dict[str, Any]) -> str:
    micro = report["micro"]
    exact = report["exact_match"]
    lines = [
        "TrustForge DataLease classifier benchmark",
        "========================================",
        f"Samples: {report['samples']}",
        (
            "Micro: "
            f"precision={micro['precision']:.3f} "
            f"recall={micro['recall']:.3f} "
            f"f1={micro['f1']:.3f}"
        ),
        f"Exact-set match: {exact['count']}/{report['samples']} ({exact['rate']:.3f})",
        "",
        "Mismatches:",
    ]
    mismatches = [case for case in report["cases"] if not case["exact"]]
    if not mismatches:
        lines.append("  none")
    else:
        for case in mismatches:
            lines.append(
                f"  - {case['id']}: "
                f"FP={case['false_positive'] or '-'} "
                f"FN={case['false_negative'] or '-'}"
            )
    return "\n".join(lines)


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
