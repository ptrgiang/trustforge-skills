from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".bash",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".xml",
}

CAPABILITY_PATTERNS: dict[str, tuple[str, ...]] = {
    "network": (
        r"\brequests\.(?:get|post|put|patch|delete)\b",
        r"\bhttpx\.", r"\burllib\.", r"\bsocket\.", r"\bcurl\b", r"\bwget\b",
        r"https?://",
    ),
    "subprocess": (
        r"\bsubprocess\.", r"\bos\.system\b", r"\bPopen\s*\(", r"\bshell=True\b",
        r"\bchild_process\b",
    ),
    "environment_read": (
        r"\bos\.environ\b", r"\bos\.getenv\b", r"\bprocess\.env\b", r"\$\{?[A-Z][A-Z0-9_]{2,}\}?",
    ),
    "filesystem_read": (
        r"\bopen\s*\(", r"\.read_text\s*\(", r"\.read_bytes\s*\(", r"\bfs\.readFile",
    ),
    "filesystem_write": (
        r"\.write_text\s*\(", r"\.write_bytes\s*\(", r"\bfs\.writeFile", r"\bshutil\.(?:copy|move|rmtree)\b",
        r"\bos\.(?:remove|unlink|rename)\b",
    ),
    "dynamic_execution": (
        r"\beval\s*\(", r"\bexec\s*\(", r"\bcompile\s*\(", r"\bFunction\s*\(",
    ),
    "credential_material": (
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|private[_-]?key)\b",
    ),
}

RISK_WEIGHTS = {
    "network": 2,
    "subprocess": 4,
    "environment_read": 2,
    "filesystem_read": 1,
    "filesystem_write": 3,
    "dynamic_execution": 5,
    "credential_material": 3,
}


@dataclass(frozen=True)
class Snapshot:
    root: str
    files: dict[str, str]
    capabilities: dict[str, list[str]]
    domains: list[str]


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"SKILL.md", "Dockerfile", "Makefile"}:
            yield path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot(root: str | Path) -> Snapshot:
    base = Path(root).resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Skill path must be a directory: {base}")

    files: dict[str, str] = {}
    evidence: dict[str, set[str]] = {key: set() for key in CAPABILITY_PATTERNS}
    domains: set[str] = set()

    for path in _iter_text_files(base):
        rel = path.relative_to(base).as_posix()
        text = _read_text(path)
        files[rel] = _sha256(text)

        for capability, patterns in CAPABILITY_PATTERNS.items():
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                evidence[capability].add(rel)

        for match in re.finditer(r"https?://([^/\s)'\"<>]+)", text, flags=re.IGNORECASE):
            domains.add(match.group(1).lower().rstrip(".,;:"))

    return Snapshot(
        root=str(base),
        files=files,
        capabilities={k: sorted(v) for k, v in evidence.items() if v},
        domains=sorted(domains),
    )


def compare(before: str | Path, after: str | Path) -> dict:
    old = snapshot(before)
    new = snapshot(after)

    old_files = set(old.files)
    new_files = set(new.files)
    added_files = sorted(new_files - old_files)
    removed_files = sorted(old_files - new_files)
    changed_files = sorted(
        path for path in old_files & new_files if old.files[path] != new.files[path]
    )

    old_caps = set(old.capabilities)
    new_caps = set(new.capabilities)
    added_caps = sorted(new_caps - old_caps)
    removed_caps = sorted(old_caps - new_caps)
    added_domains = sorted(set(new.domains) - set(old.domains))
    removed_domains = sorted(set(old.domains) - set(new.domains))

    score = sum(RISK_WEIGHTS.get(cap, 1) for cap in added_caps)
    score += min(len(added_domains), 3)
    if score >= 7:
        risk = "high"
    elif score >= 3:
        risk = "medium"
    elif score > 0:
        risk = "low"
    else:
        risk = "none"

    return {
        "before": old.root,
        "after": new.root,
        "files": {
            "added": added_files,
            "removed": removed_files,
            "changed": changed_files,
        },
        "capabilities": {
            "added": added_caps,
            "removed": removed_caps,
            "evidence_after": new.capabilities,
        },
        "network_domains": {
            "added": added_domains,
            "removed": removed_domains,
        },
        "risk": {"level": risk, "score": score},
    }


def render_text(report: dict) -> str:
    lines = [
        "TrustForge SkillDiff",
        "====================",
        f"Risk: {report['risk']['level'].upper()} (score={report['risk']['score']})",
        "",
    ]
    for section, key in (("Added capabilities", "added"), ("Removed capabilities", "removed")):
        values = report["capabilities"][key]
        lines.append(f"{section}: {', '.join(values) if values else 'none'}")
    lines.append(f"Added domains: {', '.join(report['network_domains']['added']) if report['network_domains']['added'] else 'none'}")
    lines.append("")
    for key in ("added", "removed", "changed"):
        values = report["files"][key]
        lines.append(f"Files {key}: {len(values)}")
        lines.extend(f"  - {value}" for value in values)
    return "\n".join(lines)


def dumps(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
