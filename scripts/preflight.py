from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print("\n$", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def check_version() -> None:
    import trustforge

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE).group(1)
    if trustforge.__version__ != version:
        raise RuntimeError(f"version mismatch: pyproject={version}, runtime={trustforge.__version__}")
    print(f"version consistent: {version}")


def main() -> int:
    python = sys.executable

    run(python, "-m", "unittest", "discover", "-s", "tests", "-v")

    run(
        python,
        "-m",
        "trustforge.cli",
        "verify",
        "examples/refactor-contract.json",
        "--evidence",
        "examples/refactor-evidence.json",
    )

    partial = subprocess.run(
        [
            python,
            "-m",
            "trustforge.cli",
            "verify",
            "examples/commitmentguard/release-contract.json",
            "--evidence",
            "examples/commitmentguard/release-evidence.json",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if partial.returncode != 3:
        raise RuntimeError(f"CommitmentGuard strict partial gate expected exit 3, got {partial.returncode}")
    partial_report = json.loads(partial.stdout)
    if partial_report["completion_state"] != "partial" or not partial_report["required_satisfied"]:
        raise RuntimeError("CommitmentGuard partial example did not preserve required-satisfied semantics")

    run(
        python,
        "-m",
        "trustforge.cli",
        "verify",
        "examples/commitmentguard/release-contract.json",
        "--evidence",
        "examples/commitmentguard/release-evidence.json",
        "--accept-partial",
    )

    run(
        python,
        "-m",
        "trustforge.cli",
        "datalease",
        "benchmark",
        "--dataset",
        "evals/datalease/classifier-benchmark.jsonl",
        "--min-precision",
        "0.90",
        "--min-recall",
        "0.85",
    )
    run(
        python,
        "-m",
        "trustforge.cli",
        "datalease",
        "benchmark",
        "--dataset",
        "evals/datalease/classifier-benchmark-multilingual.jsonl",
        "--min-precision",
        "0.90",
        "--min-recall",
        "0.90",
    )
    run(
        python,
        "-m",
        "trustforge.cli",
        "freshplan",
        "benchmark",
        "--nodes",
        "1000",
        "5000",
        "10000",
        "--repeats",
        "2",
        "--max-median-ms",
        "5000",
    )
    run(
        python,
        "-m",
        "trustforge.cli",
        "reprocapsule",
        "benchmark-redaction",
        "--dataset",
        "evals/reprocapsule/redaction-benchmark.jsonl",
        "--min-secret-recall",
        "1.0",
        "--min-clean-specificity",
        "1.0",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        capsule = tmp_path / "capsule"
        exported = tmp_path / "container"

        run(
            python,
            "-m",
            "trustforge.cli",
            "reprocapsule",
            "build",
            "--spec",
            "examples/reprocapsule/example-spec.yaml",
            "--output",
            str(capsule),
        )
        output = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "reprocapsule",
                "replay",
                "--capsule",
                str(capsule),
                "--execute",
                "--fail-on-divergence",
                "--json",
            ],
            cwd=ROOT,
            text=True,
        )
        report = json.loads(output)
        if report["decision"] != "reproduced":
            raise RuntimeError(f"ReproCapsule replay did not reproduce: {report['decision']}")

        container_preflight = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "reprocapsule",
                "replay-container",
                "--capsule",
                str(capsule),
                "--json",
            ],
            cwd=ROOT,
            text=True,
        )
        container_report = json.loads(container_preflight)
        if container_report["decision"] != "ready" or container_report["executed"]:
            raise RuntimeError("ReproCapsule container preflight unexpectedly executed Docker")

        run(
            python,
            "-m",
            "trustforge.cli",
            "reprocapsule",
            "export-container",
            "--capsule",
            str(capsule),
            "--output",
            str(exported),
        )

    check_version()
    print("\nPreflight passed. Safe to push / mark PR ready for CI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
