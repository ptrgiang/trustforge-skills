from __future__ import annotations

import json
from pathlib import Path

from . import skilldiff as v02
from .ast_detectors import compare_python_ast


def _evidence_from_ast(finding: dict[str, object]) -> dict[str, object]:
    return {
        "path": finding["path"],
        "line": finding["line"],
        "excerpt": finding["excerpt"],
        "detector": finding["detector"],
        "confidence": finding["confidence"],
        "symbol": finding["symbol"],
    }


def compare(before: str | Path, after: str | Path) -> dict:
    report = v02.compare(before, after)
    ast_report = compare_python_ast(before, after)

    existing_added = set(report["capabilities"]["added"])
    ast_new = set(ast_report["new_capabilities"])
    ast_only = sorted(ast_new - existing_added)

    if ast_only:
        report["capabilities"]["added"] = sorted(existing_added | set(ast_only))
        for finding in ast_report["added_findings"]:
            capability = str(finding["capability"])
            if capability not in ast_only:
                continue
            report["capabilities"]["evidence_after"].setdefault(capability, []).append(
                _evidence_from_ast(finding)
            )

        extra_score = sum(v02.RISK_WEIGHTS.get(capability, 1) for capability in ast_only)
        report["risk"]["score"] += extra_score
        report["risk"]["level"] = v02._risk_level(report["risk"]["score"])
        report["risk"]["explanations"].append(
            "Python AST analysis found new capabilities missed by the lexical detector: "
            + ", ".join(ast_only)
            + "."
        )

    parse_errors = ast_report["parse_errors_after"]
    if parse_errors:
        report["risk"]["explanations"].append(
            f"Python AST analysis could not parse {len(parse_errors)} candidate file(s); review coverage manually."
        )

    report["schema_version"] = "0.3"
    report["detectors"] = ["lexical-v0.2", "python-ast-v1"]
    report["ast_analysis"] = {
        **ast_report,
        "ast_only_new_capabilities": ast_only,
    }
    return report


def render_text(report: dict) -> str:
    base = v02.render_text(report)
    ast_report = report.get("ast_analysis", {})
    added_findings = ast_report.get("added_findings", [])
    lines = [
        base,
        "",
        "Python AST analysis:",
        f"  Files scanned: {ast_report.get('files_scanned_after', 0)}",
        f"  New AST capabilities: {', '.join(ast_report.get('new_capabilities', [])) or 'none'}",
        f"  AST-only new capabilities: {', '.join(ast_report.get('ast_only_new_capabilities', [])) or 'none'}",
        f"  New call signatures: {len(ast_report.get('added_signatures', []))}",
    ]
    parse_errors = ast_report.get("parse_errors_after", [])
    lines.append(f"  Parse errors: {len(parse_errors)}")

    if added_findings:
        lines.append("  Added AST findings:")
        for finding in added_findings[:10]:
            lines.append(
                "    - "
                f"{finding['capability']}: {finding['path']}:{finding['line']} "
                f"[{finding['confidence']}] {finding['symbol']}"
            )
    return "\n".join(lines)


def dumps(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def to_sarif(report: dict) -> dict:
    sarif = v02.to_sarif(report)
    results = sarif["runs"][0]["results"]
    sarif["runs"][0]["tool"]["driver"]["version"] = "0.3.0"

    severity_map = {
        "network": "warning",
        "subprocess": "error",
        "environment_read": "warning",
        "filesystem_read": "note",
        "filesystem_write": "warning",
        "dynamic_execution": "error",
        "credential_material": "error",
    }

    for finding in report.get("ast_analysis", {}).get("added_findings", []):
        results.append(
            {
                "ruleId": f"trustforge.python-ast.{finding['capability']}",
                "level": severity_map.get(str(finding["capability"]), "warning"),
                "message": {
                    "text": (
                        f"Python AST detector found new {finding['capability']} primitive: "
                        f"{finding['symbol']}"
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding["path"]},
                            "region": {"startLine": finding["line"]},
                        }
                    }
                ],
                "properties": {
                    "detector": finding["detector"],
                    "confidence": finding["confidence"],
                },
            }
        )
    return sarif


def dumps_sarif(report: dict) -> str:
    return json.dumps(to_sarif(report), indent=2, sort_keys=True)
