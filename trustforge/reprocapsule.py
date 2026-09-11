from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Any

import yaml


class ReproCapsuleError(ValueError):
    """Raised when a reproduction capsule cannot be built safely."""


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
        raise ReproCapsuleError(f"input path must be relative and stay inside the spec directory: {value}")
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

    # Remove bearer payloads first. Otherwise an "Authorization: Bearer ..." line
    # can be partially consumed by the generic key/value redactor.
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


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_text(report: dict[str, Any]) -> str:
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
