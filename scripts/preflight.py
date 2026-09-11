from __future__ import annotations

import json
import os
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
        "--as-of",
        "2026-09-11T14:01:00Z",
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
            "--as-of",
            "2026-09-11T14:01:00Z",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if partial.returncode != 3:
        raise RuntimeError(f"CommitmentGuard strict partial gate expected exit 3, got {partial.returncode}: {partial.stderr}")
    partial_report = json.loads(partial.stdout)
    if partial_report["completion_state"] != "partial" or not partial_report["required_satisfied"]:
        raise RuntimeError("CommitmentGuard partial example did not preserve required-satisfied semantics")
    if partial_report["summary"]["required_blockers"] != 0:
        raise RuntimeError("CommitmentGuard partial example unexpectedly has required blockers")

    run(
        python,
        "-m",
        "trustforge.cli",
        "verify",
        "examples/commitmentguard/release-contract.json",
        "--evidence",
        "examples/commitmentguard/release-evidence.json",
        "--as-of",
        "2026-09-11T14:01:00Z",
        "--accept-partial",
    )

    adversarial = subprocess.run(
        [
            python,
            "-m",
            "trustforge.cli",
            "verify",
            "evals/commitmentguard/adversarial-evidence/contract.json",
            "--evidence",
            "evals/commitmentguard/adversarial-evidence/evidence.json",
            "--as-of",
            "2026-09-11T14:00:00Z",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if adversarial.returncode != 3:
        raise RuntimeError(f"CommitmentGuard adversarial gate expected exit 3, got {adversarial.returncode}: {adversarial.stderr}")
    adversarial_report = json.loads(adversarial.stdout)
    expected = json.loads((ROOT / "evals/commitmentguard/adversarial-evidence/expected.json").read_text(encoding="utf-8"))
    if adversarial_report["completion_state"] != expected["completion_state"]:
        raise RuntimeError("CommitmentGuard adversarial completion state mismatch")
    if adversarial_report["required_satisfied"] != expected["required_satisfied"]:
        raise RuntimeError("CommitmentGuard adversarial required-satisfied mismatch")
    if adversarial_report["summary"] != expected["summary"]:
        raise RuntimeError("CommitmentGuard adversarial summary mismatch")
    actual_statuses = {item["id"]: item["status"] for item in adversarial_report["commitments"]}
    if actual_statuses != expected["statuses"]:
        raise RuntimeError(f"CommitmentGuard adversarial statuses mismatch: {actual_statuses}")

    command_evidence = subprocess.check_output(
        [
            python,
            "-m",
            "trustforge.cli",
            "evidence",
            "command",
            "--key",
            "tests.passed",
            "--observed-at",
            "2026-09-11T14:30:00Z",
            "--",
            python,
            "-c",
            "raise SystemExit(0)",
        ],
        cwd=ROOT,
        text=True,
    )
    command_bundle = json.loads(command_evidence)
    command_observation = command_bundle["observations"]["tests.passed"]
    if command_observation["value"] is not True:
        raise RuntimeError("CommitmentGuard command adapter did not map exit 0 to true")
    if command_observation["source"]["kind"] != "command":
        raise RuntimeError("CommitmentGuard command adapter source kind mismatch")
    if command_observation["source"]["stdout_captured"] or command_observation["source"]["stderr_captured"]:
        raise RuntimeError("CommitmentGuard command adapter unexpectedly captured output")

    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        github_evidence = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "evidence",
                "github-actions",
                "--key",
                "ci.passed",
                "--conclusion",
                "success",
                "--observed-at",
                "2026-09-11T14:55:00Z",
            ],
            cwd=ROOT,
            text=True,
        )
        github_bundle = json.loads(github_evidence)
        github_observation = github_bundle["observations"]["ci.passed"]
        github_source = github_observation["source"]
        if github_observation["value"] is not True:
            raise RuntimeError("CommitmentGuard GitHub Actions adapter did not map success to true")
        if github_source["kind"] != "github-actions":
            raise RuntimeError("CommitmentGuard GitHub Actions source kind mismatch")
        if github_source["run_id"] != os.environ.get("GITHUB_RUN_ID"):
            raise RuntimeError("CommitmentGuard GitHub Actions run ID provenance mismatch")
        if any("token" in key.lower() for key in github_source):
            raise RuntimeError("CommitmentGuard GitHub Actions provenance unexpectedly contains a token field")

    with tempfile.TemporaryDirectory() as evidence_tmp:
        evidence_tmp_path = Path(evidence_tmp)
        artifact = evidence_tmp_path / "coverage.json"
        artifact.write_text('{"totals":{"percent":94.5}}\n', encoding="utf-8")
        artifact_evidence = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "evidence",
                "json-artifact",
                "--key",
                "tests.coverage",
                "--input",
                str(artifact),
                "--value-path",
                "totals.percent",
                "--observed-at",
                "2026-09-11T14:30:00Z",
            ],
            cwd=ROOT,
            text=True,
        )
        artifact_bundle = json.loads(artifact_evidence)
        artifact_observation = artifact_bundle["observations"]["tests.coverage"]
        if artifact_observation["value"] != 94.5:
            raise RuntimeError("CommitmentGuard artifact adapter extracted the wrong value")
        if artifact_observation["source"]["kind"] != "artifact" or len(artifact_observation["source"]["sha256"]) != 64:
            raise RuntimeError("CommitmentGuard artifact adapter provenance mismatch")

        manifest_evidence = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "evidence",
                "package-manifest",
                "--input",
                "pyproject.toml",
                "--observed-at",
                "2026-09-11T15:20:00Z",
            ],
            cwd=ROOT,
            text=True,
        )
        manifest_bundle = json.loads(manifest_evidence)
        manifest_observation = manifest_bundle["observations"]["dependencies.manifest_sha256"]
        if len(manifest_observation["value"]) != 64:
            raise RuntimeError("CommitmentGuard package-manifest adapter did not emit a SHA-256 value")
        if manifest_observation["source"]["kind"] != "package-manifest":
            raise RuntimeError("CommitmentGuard package-manifest source kind mismatch")

        before_api = evidence_tmp_path / "api-before.json"
        after_api = evidence_tmp_path / "api-after.json"
        before_api.write_text('{"paths":{"/users":{"get":{}}}}', encoding="utf-8")
        after_api.write_text('{"paths":{"/users":{"get":{}},"/health":{"get":{}}}}', encoding="utf-8")
        api_evidence = subprocess.check_output(
            [
                python,
                "-m",
                "trustforge.cli",
                "evidence",
                "api-diff",
                "--before",
                str(before_api),
                "--after",
                str(after_api),
                "--observed-at",
                "2026-09-11T15:20:00Z",
            ],
            cwd=ROOT,
            text=True,
        )
        api_bundle = json.loads(api_evidence)
        api_observation = api_bundle["observations"]["api.no_removed_operations"]
        if api_observation["value"] is not True:
            raise RuntimeError("CommitmentGuard API diff adapter incorrectly reported an additive change")
        if api_observation["source"]["removed_operation_count"] != 0:
            raise RuntimeError("CommitmentGuard API diff removed-operation count mismatch")
        if "/users" in api_evidence or "/health" in api_evidence:
            raise RuntimeError("CommitmentGuard API diff evidence unexpectedly copied endpoint names")

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
