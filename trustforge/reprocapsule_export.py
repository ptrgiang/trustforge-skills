from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .reprocapsule import ReproCapsuleError, _load_manifest, _safe_relative_path, verify_integrity


def _python_base_image(manifest: dict[str, Any]) -> str:
    version = str(manifest.get("environment_fingerprint", {}).get("python", ""))
    parts = version.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        raise ReproCapsuleError("capsule does not contain a usable Python runtime fingerprint")
    return f"python:{parts[0]}.{parts[1]}-slim"


def _copy_verified_file(capsule: Path, relative: str, destination_root: Path) -> None:
    rel = _safe_relative_path(relative)
    source = (capsule / rel).resolve()
    try:
        source.relative_to(capsule)
    except ValueError as exc:
        raise ReproCapsuleError(f"export source escapes capsule: {relative}") from exc
    if not source.is_file():
        raise ReproCapsuleError(f"verified export source is missing: {relative}")
    destination = destination_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def export_container(capsule_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    capsule, manifest = _load_manifest(capsule_dir)
    integrity = verify_integrity(capsule)
    if integrity["decision"] != "verified":
        return {
            "schema_version": "0.1",
            "name": manifest.get("name"),
            "decision": "blocked",
            "reason": "integrity_failed",
            "integrity": integrity,
            "files": [],
        }

    output = Path(output_dir).resolve()
    if output == capsule or output in capsule.parents:
        raise ReproCapsuleError("container export output cannot be the capsule directory or one of its parents")
    if output.exists():
        if not output.is_dir():
            raise ReproCapsuleError("container export output must be a directory")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    for item in manifest.get("inputs", []):
        copied = item.get("copied_path") if isinstance(item, dict) else None
        if copied:
            _copy_verified_file(capsule, str(copied), output)

    trace = manifest.get("trace")
    if isinstance(trace, dict) and trace.get("path"):
        _copy_verified_file(capsule, str(trace["path"]), output)

    shutil.copyfile(capsule / "reprocapsule.json", output / "reprocapsule.json")

    base_image = _python_base_image(manifest)
    command = manifest.get("command", [])
    command_json = json.dumps(command)
    workdir = str(manifest.get("working_directory", "."))
    container_workdir = "/workspace" if workdir == "." else f"/workspace/{workdir}"

    dockerfile = "\n".join(
        [
            f"FROM {base_image}",
            "",
            "RUN useradd --create-home --uid 10001 repro",
            "WORKDIR /workspace",
            "COPY --chown=repro:repro inputs/ /workspace/",
            "USER repro",
            f"WORKDIR {container_workdir}",
            f"CMD {command_json}",
            "",
        ]
    )
    (output / "Dockerfile").write_text(dockerfile, encoding="utf-8")

    dockerignore = "\n".join(
        ["*", "!inputs/", "!inputs/**", "!Dockerfile", "!reprocapsule.json", "!trace.txt", ""]
    )
    (output / ".dockerignore").write_text(dockerignore, encoding="utf-8")

    devcontainer_dir = output / ".devcontainer"
    devcontainer_dir.mkdir(parents=True, exist_ok=True)
    devcontainer = {
        "name": f"TrustForge ReproCapsule: {manifest.get('name', 'reproduction')}",
        "build": {"dockerfile": "../Dockerfile", "context": ".."},
        "workspaceFolder": container_workdir,
        "remoteUser": "repro",
    }
    (devcontainer_dir / "devcontainer.json").write_text(
        json.dumps(devcontainer, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    files = [
        ".dockerignore",
        ".devcontainer/devcontainer.json",
        "Dockerfile",
        "reprocapsule.json",
        "container-export.json",
    ]
    if trace:
        files.append("trace.txt")
    files.extend(
        str(Path(str(item["copied_path"])))
        for item in manifest.get("inputs", [])
        if isinstance(item, dict) and item.get("copied_path")
    )

    report = {
        "schema_version": "0.1",
        "name": manifest.get("name"),
        "decision": "exported",
        "format": "docker-devcontainer",
        "base_image": base_image,
        "workspace": container_workdir,
        "files": sorted(set(files)),
        "safety": {
            "integrity_verified_before_export": True,
            "raw_environment_values_included": False,
            "container_built_during_export": False,
            "container_executed_during_export": False,
            "security_sandbox_claimed": False,
        },
    }
    (output / "container-export.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def render_export_text(report: dict[str, Any]) -> str:
    lines = [
        f"ReproCapsule container export: {report.get('name')}",
        f"Decision: {report.get('decision')}",
    ]
    if report.get("decision") == "exported":
        lines.extend(
            [
                f"Format: {report.get('format')}",
                f"Base image: {report.get('base_image')}",
                f"Workspace: {report.get('workspace')}",
                f"Files: {len(report.get('files', []))}",
                "Container built during export: no",
                "Container executed during export: no",
            ]
        )
    if report.get("reason"):
        lines.append(f"Reason: {report['reason']}")
    return "\n".join(lines)
