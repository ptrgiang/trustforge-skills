from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml


class ReproCapsuleError(ValueError):
    """Raised when a reproduction capsule cannot be built or replayed safely."""


SECRET_FIELD_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|private[_-]?key)"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|private[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
GENERIC_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b")
SENSITIVE_BASENAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "service-account.json",
}
SAFE_REPLAY_ENV = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "HOME",
    "USERPROFILE",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "PYTHONIOENCODING",
)


def _load_document(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReproCapsuleError(str(exc)) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ReproCapsuleError(f"invalid YAML/JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ReproCapsuleError("spec must be an object")
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ReproCapsuleError(f"path must be relative and stay inside its capsule/spec directory: {value}")
    return path


def _validate_command(command: Any) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ReproCapsuleError("command must be a non-empty list of strings")

    for index, token in enumerate(command):
        if SECRET_FIELD_RE.search(token):
            if "=" in token or ":" in token:
                raise ReproCapsuleError("command contains a secret-like inline argument; pass secrets through runtime environment instead")
            if index + 1 < len(command) and not command[index + 1].startswith("-"):
                raise ReproCapsuleError("command contains a secret-like argument with a value; pass secrets through runtime environment instead")
        if BEARER_RE.search(token) or AWS_KEY_RE.search(token) or GENERIC_TOKEN_RE.search(token):
            raise ReproCapsuleError("command appears to contain credential material")
    return list(command)


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "name",
        "command",
        "expected_exit_code",
        "expected_failure_signature",
        "working_directory",
        "trace_file",
        "inputs",
        "environment",
    }
    unknown = sorted(set(spec) - allowed)
    if unknown:
        raise ReproCapsuleError(f"unknown spec fields: {', '.join(unknown)}")
    if str(spec.get("schema_version", "0.1")) != "0.1":
        raise ReproCapsuleError("schema_version must be 0.1")
    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ReproCapsuleError("name must be a non-empty string")
    _validate_command(spec.get("command"))
    expected_exit = spec.get("expected_exit_code")
    if expected_exit is not None and (not isinstance(expected_exit, int) or isinstance(expected_exit, bool)):
        raise ReproCapsuleError("expected_exit_code must be an integer")
    signature = spec.get("expected_failure_signature")
    if signature is not None and (not isinstance(signature, str) or not signature):
        raise ReproCapsuleError("expected_failure_signature must be a non-empty string")
    working_directory = spec.get("working_directory", ".")
    if working_directory != ".":
        _safe_relative_path(str(working_directory))
    trace_file = spec.get("trace_file")
    if trace_file is not None:
        _safe_relative_path(str(trace_file))
    inputs = spec.get("inputs", [])
    if not isinstance(inputs, list):
        raise ReproCapsuleError("inputs must be a list")
    for item in inputs:
        if not isinstance(item, dict) or set(item) - {"path", "copy", "required"}:
            raise ReproCapsuleError("each input must contain only path, copy, and required")
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise ReproCapsuleError("each input.path must be a non-empty string")
        _safe_relative_path(item["path"])
        for key in ("copy", "required"):
            if key in item and not isinstance(item[key], bool):
                raise ReproCapsuleError(f"input.{key} must be boolean")
    environment = spec.get("environment", {})
    if not isinstance(environment, dict) or set(environment) - {"include"}:
        raise ReproCapsuleError("environment supports only include")
    include = environment.get("include", [])
    if not isinstance(include, list) or not all(isinstance(item, str) and item for item in include):
        raise ReproCapsuleError("environment.include must be a list of variable names")
    return spec


def sanitize_trace(text: str) -> tuple[str, int]:
    redactions = 0

    text, count = BEARER_RE.subn("Bearer [REDACTED]", text)
    redactions += count

    def assignment(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return f"{match.group(1)}=[REDACTED]"

    text = SECRET_ASSIGNMENT_RE.sub(assignment, text)
    for regex, replacement in (
        (AWS_KEY_RE, "[REDACTED_AWS_KEY]"),
        (GENERIC_TOKEN_RE, "[REDACTED_TOKEN]"),
    ):
        text, count = regex.subn(replacement, text)
        redactions += count
    return text, redactions


def _sensitive_input(path: Path) -> bool:
    lowered = path.name.casefold()
    if lowered in SENSITIVE_BASENAMES:
        return True
    return any(part.casefold() in {".ssh", ".aws", ".gnupg"} for part in path.parts)


def build_capsule(spec_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    spec_source = Path(spec_path).resolve()
    spec = validate_spec(_load_document(spec_source))
    base = spec_source.parent
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs_dir = output / "inputs"

    input_records: list[dict[str, Any]] = []
    for item in spec.get("inputs", []):
        rel = _safe_relative_path(item["path"])
        source = (base / rel).resolve()
        try:
            source.relative_to(base.resolve())
        except ValueError as exc:
            raise ReproCapsuleError(f"input escapes spec directory: {rel}") from exc
        required = item.get("required", True)
        if not source.exists():
            if required:
                raise ReproCapsuleError(f"required input does not exist: {rel}")
            input_records.append({"path": str(rel), "present": False, "required": False})
            continue
        if not source.is_file():
            raise ReproCapsuleError(f"input must be a regular file: {rel}")
        if _sensitive_input(rel):
            raise ReproCapsuleError(f"refusing to package sensitive input path: {rel}")
        data = source.read_bytes()
        record: dict[str, Any] = {
            "path": str(rel),
            "present": True,
            "required": required,
            "size_bytes": len(data),
            "sha256": _sha256_bytes(data),
        }
        if item.get("copy", True):
            destination = inputs_dir / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            record["copied_path"] = str(Path("inputs") / rel)
        input_records.append(record)

    trace_record: dict[str, Any] | None = None
    trace_file = spec.get("trace_file")
    if trace_file:
        trace_rel = _safe_relative_path(str(trace_file))
        trace_source = (base / trace_rel).resolve()
        try:
            trace_source.relative_to(base.resolve())
        except ValueError as exc:
            raise ReproCapsuleError("trace_file escapes spec directory") from exc
        if not trace_source.is_file():
            raise ReproCapsuleError(f"trace_file does not exist: {trace_rel}")
        raw_trace = trace_source.read_text(encoding="utf-8", errors="replace")
        sanitized, redactions = sanitize_trace(raw_trace)
        trace_output = output / "trace.txt"
        trace_output.write_text(sanitized, encoding="utf-8")
        trace_bytes = sanitized.encode("utf-8")
        trace_record = {
            "source": str(trace_rel),
            "path": "trace.txt",
            "sanitized": True,
            "redactions": redactions,
            "size_bytes": len(trace_bytes),
            "sha256": _sha256_bytes(trace_bytes),
        }

    env_names = spec.get("environment", {}).get("include", [])
    environment = {name: {"present": name in os.environ} for name in sorted(set(env_names))}

    manifest: dict[str, Any] = {
        "schema_version": "0.1",
        "name": spec["name"],
        "command": _validate_command(spec["command"]),
        "expected_exit_code": spec.get("expected_exit_code"),
        "expected_failure_signature": spec.get("expected_failure_signature"),
        "working_directory": spec.get("working_directory", "."),
        "environment_fingerprint": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        },
        "environment_presence": environment,
        "inputs": input_records,
        "trace": trace_record,
        "safety": {
            "raw_environment_values_included": False,
            "trace_sanitized": trace_record is not None,
            "command_executed_during_build": False,
        },
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (output / "reprocapsule.json").write_text(manifest_text, encoding="utf-8")
    return manifest


def _load_manifest(capsule_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    capsule = Path(capsule_dir).resolve()
    manifest_path = capsule / "reprocapsule.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproCapsuleError(f"cannot load capsule manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "0.1":
        raise ReproCapsuleError("unsupported or malformed capsule manifest")
    _validate_command(manifest.get("command"))
    return capsule, manifest


def verify_integrity(capsule_dir: str | Path) -> dict[str, Any]:
    capsule, manifest = _load_manifest(capsule_dir)
    checks: list[dict[str, Any]] = []
    ok = True

    for item in manifest.get("inputs", []):
        if not isinstance(item, dict):
            raise ReproCapsuleError("malformed input record in manifest")
        if not item.get("present"):
            continue
        copied = item.get("copied_path")
        if not copied:
            checks.append({"path": item.get("path"), "kind": "input", "ok": False, "reason": "not_packaged"})
            ok = False
            continue
        rel = _safe_relative_path(str(copied))
        target = (capsule / rel).resolve()
        try:
            target.relative_to(capsule)
        except ValueError as exc:
            raise ReproCapsuleError(f"packaged input escapes capsule: {copied}") from exc
        if not target.is_file():
            checks.append({"path": str(rel), "kind": "input", "ok": False, "reason": "missing"})
            ok = False
            continue
        data = target.read_bytes()
        hash_ok = _sha256_bytes(data) == item.get("sha256")
        size_ok = len(data) == item.get("size_bytes")
        item_ok = hash_ok and size_ok
        checks.append({
            "path": str(rel),
            "kind": "input",
            "ok": item_ok,
            "hash_ok": hash_ok,
            "size_ok": size_ok,
        })
        ok = ok and item_ok

    trace = manifest.get("trace")
    if trace:
        rel = _safe_relative_path(str(trace.get("path", "")))
        target = (capsule / rel).resolve()
        try:
            target.relative_to(capsule)
        except ValueError as exc:
            raise ReproCapsuleError("trace path escapes capsule") from exc
        if not target.is_file():
            checks.append({"path": str(rel), "kind": "trace", "ok": False, "reason": "missing"})
            ok = False
        else:
            data = target.read_bytes()
            hash_ok = _sha256_bytes(data) == trace.get("sha256")
            size_ok = len(data) == trace.get("size_bytes")
            trace_ok = hash_ok and size_ok
            checks.append({
                "path": str(rel),
                "kind": "trace",
                "ok": trace_ok,
                "hash_ok": hash_ok,
                "size_ok": size_ok,
            })
            ok = ok and trace_ok

    return {
        "schema_version": "0.1",
        "name": manifest.get("name"),
        "decision": "verified" if ok else "blocked",
        "checks": checks,
        "summary": {
            "checked": len(checks),
            "passed": sum(1 for item in checks if item["ok"]),
            "failed": sum(1 for item in checks if not item["ok"]),
        },
    }


def _minimal_replay_env() -> dict[str, str]:
    return {name: os.environ[name] for name in SAFE_REPLAY_ENV if name in os.environ}


def replay_capsule(
    capsule_dir: str | Path,
    *,
    execute: bool = False,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ReproCapsuleError("timeout_seconds must be greater than 0 and at most 300")

    capsule, manifest = _load_manifest(capsule_dir)
    integrity = verify_integrity(capsule)
    if integrity["decision"] != "verified":
        return {
            "schema_version": "0.1",
            "name": manifest.get("name"),
            "decision": "blocked",
            "executed": False,
            "integrity": integrity,
            "reason": "integrity_check_failed",
        }

    expected_exit = manifest.get("expected_exit_code")
    expected_signature = manifest.get("expected_failure_signature")
    if expected_exit is None and not expected_signature:
        return {
            "schema_version": "0.1",
            "name": manifest.get("name"),
            "decision": "blocked",
            "executed": False,
            "integrity": integrity,
            "reason": "no_replay_expectation",
        }

    if not execute:
        return {
            "schema_version": "0.1",
            "name": manifest.get("name"),
            "decision": "ready",
            "executed": False,
            "integrity": integrity,
            "expected_exit_code": expected_exit,
            "expected_failure_signature": expected_signature,
        }

    command = _validate_command(manifest["command"])
    working_directory = _safe_relative_path(str(manifest.get("working_directory", ".")))

    with tempfile.TemporaryDirectory(prefix="trustforge-replay-") as tmp:
        workspace = Path(tmp) / "workspace"
        inputs = capsule / "inputs"
        if inputs.exists():
            shutil.copytree(inputs, workspace)
        else:
            workspace.mkdir(parents=True)
        cwd = (workspace / working_directory).resolve()
        try:
            cwd.relative_to(workspace.resolve())
        except ValueError as exc:
            raise ReproCapsuleError("working_directory escapes replay workspace") from exc
        if not cwd.is_dir():
            return {
                "schema_version": "0.1",
                "name": manifest.get("name"),
                "decision": "blocked",
                "executed": False,
                "integrity": integrity,
                "reason": "working_directory_missing",
            }

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=_minimal_replay_env(),
                capture_output=True,
                text=True,
                shell=False,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, _ = sanitize_trace(exc.stdout or "")
            stderr, _ = sanitize_trace(exc.stderr or "")
            return {
                "schema_version": "0.1",
                "name": manifest.get("name"),
                "decision": "diverged",
                "executed": True,
                "integrity": integrity,
                "timed_out": True,
                "timeout_seconds": timeout_seconds,
                "stdout": stdout,
                "stderr": stderr,
            }
        except OSError as exc:
            raise ReproCapsuleError(f"cannot execute replay command: {exc}") from exc

    stdout, stdout_redactions = sanitize_trace(completed.stdout)
    stderr, stderr_redactions = sanitize_trace(completed.stderr)
    combined = f"{stdout}\n{stderr}"
    exit_match = expected_exit is None or completed.returncode == expected_exit
    signature_match = expected_signature is None or expected_signature in combined
    reproduced = exit_match and signature_match

    return {
        "schema_version": "0.1",
        "name": manifest.get("name"),
        "decision": "reproduced" if reproduced else "diverged",
        "executed": True,
        "integrity": integrity,
        "return_code": completed.returncode,
        "expected_exit_code": expected_exit,
        "exit_code_match": exit_match,
        "expected_failure_signature": expected_signature,
        "failure_signature_match": signature_match,
        "stdout": stdout,
        "stderr": stderr,
        "output_redactions": stdout_redactions + stderr_redactions,
        "timed_out": False,
    }


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
    if "integrity" in report:
        lines = [
            f"ReproCapsule replay: {report['name']}",
            f"Decision: {report['decision']}",
            f"Integrity: {report['integrity']['decision']}",
            f"Executed: {'yes' if report.get('executed') else 'no'}",
        ]
        if report.get("executed") and "return_code" in report:
            lines.append(f"Exit code: {report['return_code']}")
            lines.append(f"Exit code match: {'yes' if report['exit_code_match'] else 'no'}")
            if report.get("expected_failure_signature") is not None:
                lines.append(f"Failure signature match: {'yes' if report['failure_signature_match'] else 'no'}")
        if report.get("reason"):
            lines.append(f"Reason: {report['reason']}")
        return "\n".join(lines)

    trace = report.get("trace")
    lines = [
        f"ReproCapsule: {report['name']}",
        f"Command: {' '.join(report['command'])}",
        f"Inputs: {len(report['inputs'])}",
        f"Trace: {'sanitized' if trace else 'none'}",
        "Environment values: not captured",
        "Command executed during build: no",
    ]
    if trace:
        lines.append(f"Trace redactions: {trace['redactions']}")
    return "\n".join(lines)
