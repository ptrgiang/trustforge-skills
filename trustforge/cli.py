from __future__ import annotations

import argparse
import json
import sys

from .commitment_guard import render_text as render_commitments
from .commitment_guard import verify_files
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
    diff.add_argument(
        "--format",
        choices=["text", "json", "sarif"],
        default="text",
        help="Output format (default: text)",
    )
    diff.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Deprecated alias for --format json",
    )
    diff.add_argument("--fail-on", choices=["low", "medium", "high"], default=None)

    verify = sub.add_parser("verify", help="Verify commitments against an evidence JSON file")
    verify.add_argument("contract")
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--json", action="store_true", dest="as_json")

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

    return 1


if __name__ == "__main__":
    sys.exit(main())
