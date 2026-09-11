from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from .reprocapsule import ReproCapsuleError, _load_manifest, sanitize_trace, verify_integrity
from .reprocapsule_export import export_container

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _bounded_positive(value: float, *, name: str, maximum: float) -> float:
    if value <= 0 or value > maximum:
        raise ReproCapsuleError(f"{name} must be greater than 0 and at most {maximum:g}")
    return value


def _docker_runtime_args(image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--pids-limit",
        "128",
        "--memory",
        "512m",
        "--cpus",
        "1.0",
        image,
    ]


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None,
    timeout_seconds: float,
    runner: CommandRunner,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            list(command),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReproCapsuleError("Docker CLI was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReproCapsuleError(f"container operation exceeded {timeout_seconds:g}s timeout") from exc


def replay_container(
    capsule_dir: str | Path,
    *,
    execute: bool = False,
    build_timeout_seconds: float = 120.0,
    run_timeout_seconds: float = 30.0,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Verify a capsule and optionally reproduce it inside a hardened Docker container."""

    _bounded_positive(build_timeout_seconds, name="build_timeout_seconds", maximum=600)
    _bounded_positive(run_timeout_seconds, name="run_timeout_seconds", maximum=300)

    capsule, manifest = _load_manifest(capsule_dir)
    integrity = verify_integrity(capsule)
    base_report: dict[str, Any] = {
        "schema_version": "0.1",
        "name": manifest.get("name"),
        "runtime": "docker",
        "integrity": integrity,
        "executed": False,
        "container_built": False,
        "safety": {
            "build_network_disabled": True,
            "network_disabled": True,
            "read_only_rootfs": True,
            "capabilities_dropped": True,
            "no_new_privileges": True,
            "pids_limit": 128,
            "memory_limit": "512m",
            "cpu_limit": 1.0,
            "raw_environment_values_injected": False,
            "security_sandbox_claimed": False,
        },
    }
    if integrity["decision"] != "verified":
        return {**base_report, "decision": "blocked", "reason": "integrity_failed"}

    expected_exit = manifest.get("expected_exit_code")
    expected_signature = manifest.get("expected_failure_signature")
    if expected_exit is None and not expected_signature:
        return {**base_report, "decision": "blocked", "reason": "missing_replay_expectation"}

    if not execute:
        return {**base_report, "decision": "ready", "reason": "execution_not_requested"}

    with tempfile.TemporaryDirectory(prefix="trustforge-container-") as tmp:
        context = Path(tmp) / "context"
        export = export_container(capsule, context)
        if export.get("decision") != "exported":
            return {
                **base_report,
                "decision": "blocked",
                "reason": "container_export_failed",
                "export": export,
            }

        image = f"trustforge-repro:{uuid.uuid4().hex[:12]}"
        build_command = [
            "docker",
            "build",
            "--pull=false",
            "--network",
            "none",
            "--tag",
            image,
            ".",
        ]
        build = _run(build_command, cwd=context, timeout_seconds=build_timeout_seconds, runner=runner)
        build_stdout, _ = sanitize_trace(build.stdout or "")
        build_stderr, _ = sanitize_trace(build.stderr or "")
        if build.returncode != 0:
            return {
                **base_report,
                "decision": "blocked",
                "reason": "container_build_failed",
                "container_built": False,
                "build_return_code": build.returncode,
                "build_stdout": build_stdout,
                "build_stderr": build_stderr,
            }

        run_command = _docker_runtime_args(image)
        run = _run(run_command, cwd=None, timeout_seconds=run_timeout_seconds, runner=runner)
        stdout, stdout_redactions = sanitize_trace(run.stdout or "")
        stderr, stderr_redactions = sanitize_trace(run.stderr or "")
        combined = stdout + "\n" + stderr
        exit_match = expected_exit is None or run.returncode == expected_exit
        signature_match = expected_signature is None or expected_signature in combined
        reproduced = bool(exit_match and signature_match)

        try:
            runner(
                ["docker", "image", "rm", "--force", image],
                cwd=None,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass

        return {
            **base_report,
            "decision": "reproduced" if reproduced else "diverged",
            "reason": None if reproduced else "replay_expectation_mismatch",
            "executed": True,
            "container_built": True,
            "image": image,
            "return_code": run.returncode,
            "expected_exit_code": expected_exit,
            "exit_code_match": exit_match,
            "expected_failure_signature": expected_signature,
            "failure_signature_match": signature_match,
            "stdout": stdout,
            "stderr": stderr,
            "redactions": stdout_redactions + stderr_redactions,
            "docker_build": build_command,
            "docker_run": run_command,
        }


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"ReproCapsule container replay: {report.get('name')}",
        f"Decision: {report.get('decision')}",
        f"Executed: {'yes' if report.get('executed') else 'no'}",
        f"Container built: {'yes' if report.get('container_built') else 'no'}",
    ]
    if report.get("reason"):
        lines.append(f"Reason: {report['reason']}")
    if report.get("return_code") is not None:
        lines.extend(
            [
                f"Return code: {report['return_code']}",
                f"Exit code match: {'yes' if report.get('exit_code_match') else 'no'}",
                f"Failure signature match: {'yes' if report.get('failure_signature_match') else 'no'}",
            ]
        )
    return "\n".join(lines)
