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
from .freshplan import FreshPlanError, dumps as dump_freshplan, evaluate_file as evaluate_freshplan, render_text as render_freshplan
from .freshplan_benchmark import FreshPlanBenchmarkError, benchmark as benchmark_freshplan, dumps as dump_freshplan_benchmark, render_text as render_freshplan_benchmark
from .freshplan_refresh import FreshPlanRefreshError, build_plan_patch_file, build_refresh_requests_file, dumps as dump_freshplan_refresh, render_patch_text, render_requests_text
from .reprocapsule import ReproCapsuleError, build_capsule, dumps as dump_reprocapsule, replay_capsule, render_text as render_reprocapsule
from .reprocapsule_container import replay_container, render_text as render_container_replay
from .reprocapsule_eval import ReproCapsuleBenchmarkError, benchmark_file as benchmark_reprocapsule, dumps as dump_reprocapsule_benchmark, render_text as render_reprocapsule_benchmark
from .reprocapsule_export import export_container, render_export_text
from .skilldiff_v03 import compare, dumps as dump_skilldiff, dumps_sarif, render_text as render_skilldiff


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trustforge", description="Trust and verification primitives for autonomous AI agents.")
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
    apply_cmd.add_argument("--policy", required=True)
    apply_cmd.add_argument("--purpose", required=True)
    apply_cmd.add_argument("--input", required=True, dest="input_path")
    apply_cmd.add_argument("--payload-only", action="store_true")
    apply_cmd.add_argument("--audit-output", default=None)
    benchmark_cmd = datalease_sub.add_parser("benchmark", help="Evaluate the built-in classifier against a JSONL benchmark")
    benchmark_cmd.add_argument("--dataset", required=True)
    benchmark_cmd.add_argument("--json", action="store_true", dest="as_json")
    benchmark_cmd.add_argument("--min-precision", type=float, default=None)
    benchmark_cmd.add_argument("--min-recall", type=float, default=None)

    freshplan = sub.add_parser("freshplan", help="Evaluate and refresh freshness-aware dependency graphs")
    freshplan_sub = freshplan.add_subparsers(dest="freshplan_command", required=True)
    freshplan_check = freshplan_sub.add_parser("check")
    freshplan_check.add_argument("--plan", required=True)
    freshplan_check.add_argument("--as-of", default=None)
    freshplan_check.add_argument("--json", action="store_true", dest="as_json")
    freshplan_check.add_argument("--fail-on-stale", action="store_true")
    freshplan_requests = freshplan_sub.add_parser("requests")
    freshplan_requests.add_argument("--plan", required=True)
    freshplan_requests.add_argument("--as-of", default=None)
    freshplan_requests.add_argument("--json", action="store_true", dest="as_json")
    freshplan_patch = freshplan_sub.add_parser("patch")
    freshplan_patch.add_argument("--plan", required=True)
    freshplan_patch.add_argument("--evidence", required=True)
    freshplan_patch.add_argument("--as-of", default=None)
    freshplan_patch.add_argument("--json", action="store_true", dest="as_json")
    freshplan_patch.add_argument("--fail-on-replan", action="store_true")
    freshplan_bench = freshplan_sub.add_parser("benchmark")
    freshplan_bench.add_argument("--nodes", nargs="+", type=int, default=[1000, 5000, 10000])
    freshplan_bench.add_argument("--repeats", type=int, default=3)
    freshplan_bench.add_argument("--json", action="store_true", dest="as_json")
    freshplan_bench.add_argument("--max-median-ms", type=float, default=None)

    reprocapsule = sub.add_parser("reprocapsule", help="Build and verify portable failure reproductions")
    rs = reprocapsule.add_subparsers(dest="reprocapsule_command", required=True)
    build = rs.add_parser("build")
    build.add_argument("--spec", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--json", action="store_true", dest="as_json")
    replay = rs.add_parser("replay")
    replay.add_argument("--capsule", required=True)
    replay.add_argument("--execute", action="store_true")
    replay.add_argument("--timeout", type=float, default=30.0)
    replay.add_argument("--json", action="store_true", dest="as_json")
    replay.add_argument("--fail-on-divergence", action="store_true")
    export = rs.add_parser("export-container")
    export.add_argument("--capsule", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--json", action="store_true", dest="as_json")
    container_replay = rs.add_parser("replay-container", help="Verify and optionally replay a capsule inside Docker")
    container_replay.add_argument("--capsule", required=True)
    container_replay.add_argument("--execute", action="store_true", help="Explicitly allow Docker build/run")
    container_replay.add_argument("--build-timeout", type=float, default=120.0)
    container_replay.add_argument("--run-timeout", type=float, default=30.0)
    container_replay.add_argument("--json", action="store_true", dest="as_json")
    container_replay.add_argument("--fail-on-divergence", action="store_true")
    benchmark = rs.add_parser("benchmark-redaction")
    benchmark.add_argument("--dataset", required=True)
    benchmark.add_argument("--json", action="store_true", dest="as_json")
    benchmark.add_argument("--min-secret-recall", type=float, default=None)
    benchmark.add_argument("--min-clean-specificity", type=float, default=None)
    return parser


def _risk_rank(level: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}[level]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "skilldiff":
        report = compare(args.before, args.after)
        output_format = "json" if args.as_json else args.format
        print(dump_skilldiff(report) if output_format == "json" else dumps_sarif(report) if output_format == "sarif" else render_skilldiff(report))
        return 2 if args.fail_on and _risk_rank(report["risk"]["level"]) >= _risk_rank(args.fail_on) else 0
    if args.command == "verify":
        report = verify_files(args.contract, args.evidence)
        print(json.dumps(report, indent=2, sort_keys=True) if args.as_json else render_commitments(report))
        return 0 if report["verified_complete"] else 3
    if args.command == "datalease" and args.datalease_command == "apply":
        try:
            report = apply_datalease(args.policy, args.input_path, args.purpose)
        except (DataLeaseError, OSError) as exc:
            print(f"DataLease error: {exc}", file=sys.stderr); return 4
        if args.audit_output:
            p = Path(args.audit_output); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(dump_datalease(report) + "\n", encoding="utf-8")
        print(json.dumps(report["output"], indent=2, sort_keys=True) if args.payload_only and report["decision"] == "projected" else dump_datalease(report))
        return 0 if report["decision"] == "projected" else 4
    if args.command == "datalease" and args.datalease_command == "benchmark":
        for name in ("min_precision", "min_recall"):
            t = getattr(args, name)
            if t is not None and not 0 <= t <= 1: return 5
        try: report = benchmark_datalease(args.dataset)
        except (DataLeaseBenchmarkError, DataLeaseError, OSError) as exc:
            print(f"DataLease benchmark error: {exc}", file=sys.stderr); return 5
        print(dump_benchmark(report) if args.as_json else render_benchmark(report))
        return 5 if (args.min_precision is not None and report["micro"]["precision"] < args.min_precision) or (args.min_recall is not None and report["micro"]["recall"] < args.min_recall) else 0
    if args.command == "freshplan" and args.freshplan_command == "check":
        try: report = evaluate_freshplan(args.plan, as_of=args.as_of)
        except (FreshPlanError, OSError, json.JSONDecodeError) as exc:
            print(f"FreshPlan error: {exc}", file=sys.stderr); return 6
        print(dump_freshplan(report) if args.as_json else render_freshplan(report))
        return 6 if args.fail_on_stale and report["decision"] == "replan_required" else 0
    if args.command == "freshplan" and args.freshplan_command == "requests":
        try: report = build_refresh_requests_file(args.plan, as_of=args.as_of)
        except (FreshPlanRefreshError, FreshPlanError, OSError, json.JSONDecodeError) as exc:
            print(f"FreshPlan refresh error: {exc}", file=sys.stderr); return 6
        print(dump_freshplan_refresh(report) if args.as_json else render_requests_text(report)); return 0
    if args.command == "freshplan" and args.freshplan_command == "patch":
        try: report = build_plan_patch_file(args.plan, args.evidence, as_of=args.as_of)
        except (FreshPlanRefreshError, FreshPlanError, OSError, json.JSONDecodeError) as exc:
            print(f"FreshPlan refresh error: {exc}", file=sys.stderr); return 6
        print(dump_freshplan_refresh(report) if args.as_json else render_patch_text(report))
        return 6 if args.fail_on_replan and report["decision"] in {"blocked", "replan_required"} else 0
    if args.command == "freshplan" and args.freshplan_command == "benchmark":
        try: report = benchmark_freshplan(args.nodes, repeats=args.repeats)
        except (FreshPlanBenchmarkError, FreshPlanError) as exc:
            print(f"FreshPlan benchmark error: {exc}", file=sys.stderr); return 6
        print(dump_freshplan_benchmark(report) if args.as_json else render_freshplan_benchmark(report))
        return 6 if args.max_median_ms is not None and report["largest_case"]["median_ms"] > args.max_median_ms else 0
    if args.command == "reprocapsule" and args.reprocapsule_command == "build":
        try: report = build_capsule(args.spec, args.output)
        except (ReproCapsuleError, OSError) as exc:
            print(f"ReproCapsule error: {exc}", file=sys.stderr); return 7
        print(dump_reprocapsule(report) if args.as_json else render_reprocapsule(report)); return 0
    if args.command == "reprocapsule" and args.reprocapsule_command == "replay":
        try: report = replay_capsule(args.capsule, execute=args.execute, timeout_seconds=args.timeout)
        except (ReproCapsuleError, OSError) as exc:
            print(f"ReproCapsule replay error: {exc}", file=sys.stderr); return 7
        print(dump_reprocapsule(report) if args.as_json else render_reprocapsule(report))
        if args.fail_on_divergence and report["decision"] != "reproduced": return 7
        return 0 if report["decision"] not in {"blocked", "diverged"} else 7
    if args.command == "reprocapsule" and args.reprocapsule_command == "export-container":
        try: report = export_container(args.capsule, args.output)
        except (ReproCapsuleError, OSError) as exc:
            print(f"ReproCapsule container export error: {exc}", file=sys.stderr); return 7
        print(dump_reprocapsule(report) if args.as_json else render_export_text(report)); return 0 if report["decision"] == "exported" else 7
    if args.command == "reprocapsule" and args.reprocapsule_command == "replay-container":
        try:
            report = replay_container(args.capsule, execute=args.execute, build_timeout_seconds=args.build_timeout, run_timeout_seconds=args.run_timeout)
        except (ReproCapsuleError, OSError) as exc:
            print(f"ReproCapsule container replay error: {exc}", file=sys.stderr); return 7
        print(dump_reprocapsule(report) if args.as_json else render_container_replay(report))
        if args.fail_on_divergence and report["decision"] != "reproduced": return 7
        return 0 if report["decision"] not in {"blocked", "diverged"} else 7
    if args.command == "reprocapsule" and args.reprocapsule_command == "benchmark-redaction":
        for name in ("min_secret_recall", "min_clean_specificity"):
            t = getattr(args, name)
            if t is not None and not 0 <= t <= 1: return 7
        try: report = benchmark_reprocapsule(args.dataset)
        except (ReproCapsuleBenchmarkError, OSError) as exc:
            print(f"ReproCapsule benchmark error: {exc}", file=sys.stderr); return 7
        print(dump_reprocapsule_benchmark(report) if args.as_json else render_reprocapsule_benchmark(report))
        return 7 if (args.min_secret_recall is not None and report["secret_recall"] < args.min_secret_recall) or (args.min_clean_specificity is not None and report["clean_specificity"] < args.min_clean_specificity) else 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
