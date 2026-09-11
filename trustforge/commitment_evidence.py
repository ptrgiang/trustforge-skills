from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class CommitmentEvidenceError(ValueError):
    """Raised when evidence cannot be collected safely or deterministically."""


def _observed_at(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommitmentEvidenceError("observed_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CommitmentEvidenceError("observed_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bundle(key: str, value: Any, observed_at: str, source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(key, str) or not key:
        raise CommitmentEvidenceError("key must be a non-empty string")
    return {
        "schema_version": "0.2",
        "observations": {
            key: {
                "value": value,
                "observed_at": observed_at,
                "source": source,
            }
        },
    }


def _argv_fingerprint(command: Sequence[str]) -> str:
    encoded = b"\0".join(part.encode("utf-8") for part in command)
    return hashlib.sha256(encoded).hexdigest()


def _validate_command(command: Sequence[str], timeout_seconds: float) -> None:
    if not command or not all(isinstance(part, str) and part for part in command):
        raise CommitmentEvidenceError("command must be a non-empty sequence of strings")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise CommitmentEvidenceError("timeout_seconds must be greater than 0 and at most 300")


def _run_exit(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    runner: Callable[..., subprocess.CompletedProcess[Any]],
    label: str,
) -> subprocess.CompletedProcess[Any]:
    _validate_command(command, timeout_seconds)
    try:
        return runner(
            list(command),
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CommitmentEvidenceError(f"{label} evidence collection failed: {exc}") from exc


def collect_command_exit(
    key: str,
    command: Sequence[str],
    *,
    observed_at: str | None = None,
    timeout_seconds: float = 30.0,
    runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> dict[str, Any]:
    completed = _run_exit(command, timeout_seconds=timeout_seconds, runner=runner, label="command")
    return _bundle(
        key,
        completed.returncode == 0,
        _observed_at(observed_at),
        {
            "kind": "command",
            "executable": command[0],
            "argument_count": max(len(command) - 1, 0),
            "argv_sha256": _argv_fingerprint(command),
            "exit_code": completed.returncode,
            "stdout_captured": False,
            "stderr_captured": False,
        },
    )


def collect_pytest(
    key: str,
    pytest_args: Sequence[str] = (),
    *,
    python_executable: str = "python",
    observed_at: str | None = None,
    timeout_seconds: float = 120.0,
    runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> dict[str, Any]:
    if not isinstance(python_executable, str) or not python_executable:
        raise CommitmentEvidenceError("python_executable must be a non-empty string")
    if not all(isinstance(part, str) and part for part in pytest_args):
        raise CommitmentEvidenceError("pytest_args must contain only non-empty strings")

    command = [python_executable, "-m", "pytest", *pytest_args]
    completed = _run_exit(command, timeout_seconds=timeout_seconds, runner=runner, label="pytest")
    return _bundle(
        key,
        completed.returncode == 0,
        _observed_at(observed_at),
        {
            "kind": "pytest",
            "python_executable": python_executable,
            "argument_count": len(pytest_args),
            "argv_sha256": _argv_fingerprint(command),
            "exit_code": completed.returncode,
            "stdout_captured": False,
            "stderr_captured": False,
        },
    )


def collect_github_actions(
    key: str,
    conclusion: str,
    *,
    observed_at: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environment is None else environment
    normalized = conclusion.strip().lower() if isinstance(conclusion, str) else ""
    allowed = {"success", "failure", "cancelled", "skipped"}
    if normalized not in allowed:
        raise CommitmentEvidenceError(
            "GitHub Actions conclusion must be one of: success, failure, cancelled, skipped"
        )
    if str(env.get("GITHUB_ACTIONS", "")).lower() != "true":
        raise CommitmentEvidenceError("GitHub Actions evidence requires GITHUB_ACTIONS=true")

    required = {
        "repository": "GITHUB_REPOSITORY",
        "run_id": "GITHUB_RUN_ID",
        "run_attempt": "GITHUB_RUN_ATTEMPT",
        "workflow": "GITHUB_WORKFLOW",
        "job": "GITHUB_JOB",
        "sha": "GITHUB_SHA",
    }
    values: dict[str, str] = {}
    missing: list[str] = []
    for output_name, env_name in required.items():
        value = env.get(env_name)
        if not isinstance(value, str) or not value:
            missing.append(env_name)
        else:
            values[output_name] = value
    if missing:
        raise CommitmentEvidenceError(
            f"missing required GitHub Actions metadata: {', '.join(sorted(missing))}"
        )

    server_url = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    source: dict[str, Any] = {
        "kind": "github-actions",
        "conclusion": normalized,
        **values,
        "run_url": f"{server_url}/{values['repository']}/actions/runs/{values['run_id']}",
    }
    for source_key, env_name in (
        ("ref", "GITHUB_REF"),
        ("event_name", "GITHUB_EVENT_NAME"),
    ):
        value = env.get(env_name)
        if isinstance(value, str) and value:
            source[source_key] = value

    return _bundle(
        key,
        normalized == "success",
        _observed_at(observed_at),
        source,
    )


def _get_nested(value: Any, dotted_path: str) -> tuple[bool, Any]:
    current = value
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def collect_json_artifact(
    key: str,
    path: str | Path,
    value_path: str,
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    source = Path(path)
    if not value_path:
        raise CommitmentEvidenceError("value_path must be a non-empty dotted path")
    try:
        raw = source.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommitmentEvidenceError(f"cannot read JSON artifact: {exc}") from exc

    found, value = _get_nested(document, value_path)
    if not found:
        raise CommitmentEvidenceError(f"value path not found in JSON artifact: {value_path}")

    return _bundle(
        key,
        value,
        _observed_at(observed_at),
        {
            "kind": "artifact",
            "path": str(source),
            "value_path": value_path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
    )


def merge_bundles(*bundles: dict[str, Any]) -> dict[str, Any]:
    observations: dict[str, Any] = {}
    for bundle in bundles:
        if bundle.get("schema_version") != "0.2" or not isinstance(bundle.get("observations"), dict):
            raise CommitmentEvidenceError("all bundles must use CommitmentGuard evidence schema 0.2")
        for key, observation in bundle["observations"].items():
            if key in observations:
                raise CommitmentEvidenceError(f"duplicate observation key while merging: {key}")
            observations[key] = observation
    if not observations:
        raise CommitmentEvidenceError("at least one observation is required")
    return {"schema_version": "0.2", "observations": observations}


def dumps(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, indent=2, sort_keys=True)
