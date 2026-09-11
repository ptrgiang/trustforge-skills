from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .commitment_guard import render_text as render_commitments
from .commitment_guard import verify_files
from .datalease import DataLeaseError, apply_files as apply_datalease, dumps as dump_datalease
from .datalease_eval import (
    DataLeaseBenchmarkError,
    benchmark_file as benchmark_datalease,
    dumps as dump_benchmark,
    render_text as render_benchmark,
)
from .skilldiff_v03 import compare, dumps as dump_skilldiff, dumps_sarif, render_text as render_skilldiff


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trustforge",
        description="Trust and verification primitives for autonomous AI agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    diff = sub.add_parser("skilldiff", help="Compare two skill directories for trust-boundary changes")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    diff.add_argument("--json", action="store_true", dest="as_json", help="Deprecated alias for --format json")
    diff.add_argument("--fail-on", choices=["low", "medium", "high"], default=None)

    verify = sub.add_parser("verify", help="Verify commitments against an evidence JSON file")
    verify.add_argument("contract")
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--json", action="store_true", dest="as_json")

    datalease = sub.add_parser("datalease", help="Apply and evaluate purpose-bound data minimization policies")
    datalease_sub = datalease.add_subparsers(dest="datalease_command", required=True)

    apply_cmd = datalease_sub.add_parser("apply", help="Project a JSON payload through a DataLease policy")
    apply_cmd.add_argument("--policy", required=True, help="Path to a DataLease JSON/YAML policy")
    apply_cmd.add_argument("--purpose", required=True, help="Declared purpose for this data transfer")
    apply_cmd.add_argument("--input", required=True, dest="input_path", help="Path to the input JSON payload")
    apply_cmd.add_argument("--payload-only", action="store_true", help="Print only the projected payload")
    apply_cmd.add_argument("--audit-output", default=None, help="Optional path for the full decision + audit report")

    benchmark_cmd = datalease_sub.add_parser(
        "benchmark",
        help="Evaluate the built-in classifier against a JSONL benchmark",
    )
    benchmark_cmd.add_argument("--dataset", required=True, help="Path to a DataLease classifier JSONL dataset")
    benchmark_cmd.add_argument("--json", action="store_true", dest="as_json")
    benchmark_cmd.add_argument(
        "--min-precision",
        type=float,
        default=None,
        help="Exit 5 when micro precision is below this threshold",
    )
    benchmark_cmd.add_argument(
        "--min-recall",
        type=float,
        default=None,
        help="Exit 5 when micro recall is below this threshold",
    )

    return parser


def _risk_rank(level: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}[level]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "skilldiff":
        report = compare(args.before, args.after)
        output_format = "json" if args.as_json else args.format
        if output_format == "json":
            print(dump_skilldiff(report))
        elif output_format == "sarif":
            print(dumps_sarif(report))
        else:
            print(render_skilldiff(report))
        if args.fail_on and _risk_rank(report["risk"]["level"]) >= _risk_rank(args.fail_on):
            return 2
        return 0

    if args.command == "verify":
        report = verify_files(args.contract, args.evidence)
        print(json.dumps(report, indent=2, sort_keys=True) if args.as_json else render_commitments(report))
        return 0 if report["verified_complete"] else 3

    if args.command == "datalease" and args.datalease_command == "apply":
        try:
            report = apply_datalease(args.policy, args.input_path, args.purpose)
        except (DataLeaseError, OSError) as exc:
            print(f"DataLease error: {exc}", file=sys.stderr)
            return 4

        if args.audit_output:
            audit_path = Path(args.audit_output)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(dump_datalease(report) + "\n", encoding="utf-8")

        if args.payload_only and report["decision"] == "projected":
            print(json.dumps(report["output"], indent=2, sort_keys=True))
        else:
            print(dump_datalease(report))
        return 0 if report["decision"] == "projected" else 4

    if args.command == "datalease" and args.datalease_command == "benchmark":
        for name in ("min_precision", "min_recall"):
            threshold = getattr(args, name)
            if threshold is not None and not 0.0 <= threshold <= 1.0:
                print(
                    f"DataLease benchmark error: --{name.replace('_', '-')} must be between 0 and 1",
                    file=sys.stderr,
                )
                return 5
        try:
            report = benchmark_datalease(args.dataset)
        except (DataLeaseBenchmarkError, DataLeaseError, OSError) as exc:
            print(f"DataLease benchmark error: {exc}", file=sys.stderr)
            return 5

        print(dump_benchmark(report) if args.as_json else render_benchmark(report))

        micro = report["micro"]
        if args.min_precision is not None and micro["precision"] < args.min_precision:
            return 5
        if args.min_recall is not None and micro["recall"] < args.min_recall:
            return 5
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
