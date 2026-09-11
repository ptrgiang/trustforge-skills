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


def _read_bytes(path: str | Path, label: str) -> tuple[Path, bytes]:
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise CommitmentEvidenceError(f"cannot read {label}: {exc}") from exc
    if not raw:
        raise CommitmentEvidenceError(f"{label} must not be empty")
    return source, raw


def _manifest_type(path: Path) -> str:
    name = path.name.lower()
    if name == "pyproject.toml":
        return "python-pyproject"
    if name.startswith("requirements") and path.suffix.lower() in {".txt", ".in"}:
        return "python-requirements"
    if name in {"poetry.lock", "uv.lock", "pdm.lock"}:
        return f"python-{name.split('.')[0]}-lock"
    if name == "package.json":
        return "node-package"
    if name in {"package-lock.json", "npm-shrinkwrap.json"}:
        return "node-npm-lock"
    if name == "yarn.lock":
        return "node-yarn-lock"
    if name in {"pnpm-lock.yaml", "pnpm-lock.yml"}:
        return "node-pnpm-lock"
    return "generic-manifest"


def collect_package_manifest(
    key: str,
    path: str | Path,
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    source, raw = _read_bytes(path, "package manifest")
    digest = hashlib.sha256(raw).hexdigest()
    return _bundle(
        key,
        digest,
        _observed_at(observed_at),
        {
            "kind": "package-manifest",
            "path": str(source),
            "manifest_type": _manifest_type(source),
            "sha256": digest,
            "size_bytes": len(raw),
        },
    )


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _openapi_operations(document: Any) -> set[tuple[str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise CommitmentEvidenceError("API diff input must be an OpenAPI-like JSON object with a paths mapping")
    operations: set[tuple[str, str]] = set()
    for path, item in document["paths"].items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        for method in item:
            normalized = str(method).lower()
            if normalized in _HTTP_METHODS:
                operations.add((normalized.upper(), path))
    return operations


def _read_json_document(path: str | Path, label: str) -> tuple[Path, bytes, Any]:
    source, raw = _read_bytes(path, label)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommitmentEvidenceError(f"{label} must be valid UTF-8 JSON: {exc}") from exc
    return source, raw, document


def collect_api_diff(
    key: str,
    before_path: str | Path,
    after_path: str | Path,
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    before, before_raw, before_document = _read_json_document(before_path, "before API document")
    after, after_raw, after_document = _read_json_document(after_path, "after API document")
    before_ops = _openapi_operations(before_document)
    after_ops = _openapi_operations(after_document)
    removed = before_ops - after_ops
    added = after_ops - before_ops
    return _bundle(
        key,
        not removed,
        _observed_at(observed_at),
        {
            "kind": "api-diff",
            "format": "openapi-path-methods-v1",
            "before_path": str(before),
            "after_path": str(after),
            "before_sha256": hashlib.sha256(before_raw).hexdigest(),
            "after_sha256": hashlib.sha256(after_raw).hexdigest(),
            "before_size_bytes": len(before_raw),
            "after_size_bytes": len(after_raw),
            "before_operation_count": len(before_ops),
            "after_operation_count": len(after_ops),
            "removed_operation_count": len(removed),
            "added_operation_count": len(added),
            "operation_names_captured": False,
        },
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
