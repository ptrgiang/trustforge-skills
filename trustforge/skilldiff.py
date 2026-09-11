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
        r"\bos\.environ\b", r"\bos\.getenv\b", r"\bprocess\.env\b",
        r"\$\{?[A-Z][A-Z0-9_]{2,}\}?",
    ),
    "filesystem_read": (
        r"\bopen\s*\(", r"\.read_text\s*\(", r"\.read_bytes\s*\(", r"\bfs\.readFile",
    ),
    "filesystem_write": (
        r"\.write_text\s*\(", r"\.write_bytes\s*\(", r"\bfs\.writeFile",
        r"\bshutil\.(?:copy|move|rmtree)\b", r"\bos\.(?:remove|unlink|rename)\b",
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

SECRET_NAME_RE = re.compile(
    r"(?:secret|token|password|passwd|api[_-]?key|private[_-]?key|client[_-]?secret|credential)",
    re.IGNORECASE,
)

TRIGGER_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "with", "when",
    "use", "uses", "using", "this", "that", "skill", "agent", "tasks", "task", "help",
    "should", "can", "will", "be", "is", "are", "as", "from", "by", "it", "user",
}


@dataclass(frozen=True)
class Snapshot:
    root: str
    files: dict[str, str]
    capabilities: dict[str, list[dict[str, object]]]
    domains: dict[str, list[dict[str, object]]]
    trigger_text: str
    dependencies: list[str]
    secret_refs: dict[str, list[dict[str, object]]]
    manifest: dict[str, object]


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


def _evidence(rel: str, line_no: int, line: str) -> dict[str, object]:
    excerpt = line.strip()
    if len(excerpt) > 180:
        excerpt = excerpt[:177] + "..."
    return {"path": rel, "line": line_no, "excerpt": excerpt}


def _extract_trigger_text(skill_md: Path) -> str:
    if not skill_md.exists():
        return ""
    text = _read_text(skill_md)
    candidates: list[str] = []

    frontmatter = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
    if frontmatter:
        block = frontmatter.group(1)
        desc = re.search(r"(?mi)^description\s*:\s*(.+)$", block)
        if desc:
            candidates.append(desc.group(1).strip().strip("'\""))

    for line in text.splitlines():
        stripped = line.strip(" #-*\t")
        if re.search(r"\b(?:use|trigger|invoke|activate)\b.*\b(?:when|for)\b", stripped, re.IGNORECASE):
            candidates.append(stripped)

    if not candidates:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for paragraph in paragraphs:
            if not paragraph.startswith("#") and not paragraph.startswith("---"):
                candidates.append(" ".join(paragraph.split()))
                break

    return " ".join(dict.fromkeys(candidates))


def _trigger_terms(text: str) -> set[str]:
    tokens = re.findall(r"[a-z][a-z0-9_+-]{2,}", text.lower())
    return {token for token in tokens if token not in TRIGGER_STOPWORDS}


def _trigger_diff(old_text: str, new_text: str) -> dict[str, object]:
    old_terms = _trigger_terms(old_text)
    new_terms = _trigger_terms(new_text)
    added = sorted(new_terms - old_terms)
    removed = sorted(old_terms - new_terms)

    if not old_text and new_text:
        expansion = "unknown"
        ratio = None
    else:
        old_count = max(len(old_terms), 1)
        ratio = round(len(new_terms) / old_count, 2)
        if len(added) >= 8 or ratio >= 1.8:
            expansion = "high"
        elif len(added) >= 3 or ratio >= 1.25:
            expansion = "medium"
        elif added:
            expansion = "low"
        else:
            expansion = "none"

    return {
        "before": old_text,
        "after": new_text,
        "added_terms": added,
        "removed_terms": removed,
        "term_ratio": ratio,
        "estimated_expansion": expansion,
        "note": "Heuristic lexical estimate; review trigger changes semantically before trust decisions.",
    }


def _parse_requirements(text: str) -> set[str]:
    deps: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("-", "--")):
            continue
        name = re.split(r"[<>=!~;\[\s]", line, maxsplit=1)[0].strip()
        if name:
            deps.add(name.lower())
    return deps


def _parse_pyproject_dependencies(text: str) -> set[str]:
    deps: set[str] = set()
    block_match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text)
    if block_match:
        for quoted in re.findall(r"['\"]([^'\"]+)['\"]", block_match.group(1)):
            name = re.split(r"[<>=!~;\[\s]", quoted, maxsplit=1)[0].strip()
            if name:
                deps.add(name.lower())
    return deps


def _parse_package_json(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = data.get(key, {})
        if isinstance(value, dict):
            deps.update(str(name).lower() for name in value)
    return deps


def _extract_dependencies(base: Path) -> list[str]:
    deps: set[str] = set()
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.startswith("requirements") and path.suffix == ".txt":
            deps |= _parse_requirements(_read_text(path))
        elif name == "pyproject.toml":
            deps |= _parse_pyproject_dependencies(_read_text(path))
        elif name == "package.json":
            deps |= _parse_package_json(_read_text(path))
    return sorted(deps)


def _load_manifest(base: Path) -> dict[str, object]:
    candidates = [
        base / "trustforge.json",
        base / "capability-manifest.json",
        base / "trustforge.yaml",
        base / "trustforge.yml",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = _read_text(path)
        if path.suffix == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return {"path": path.name, "error": "invalid_json", "declared_capabilities": []}
            declared = data.get("capabilities", data.get("declared_capabilities", []))
            if isinstance(declared, dict):
                declared = [key for key, enabled in declared.items() if enabled]
            if not isinstance(declared, list):
                declared = []
            return {
                "path": path.name,
                "declared_capabilities": sorted({str(item) for item in declared}),
            }

        declared: list[str] = []
        in_caps = False
        for raw in text.splitlines():
            if re.match(r"^\s*(?:capabilities|declared_capabilities)\s*:\s*$", raw):
                in_caps = True
                continue
            if in_caps:
                item = re.match(r"^\s*-\s*([A-Za-z0-9_-]+)\s*$", raw)
                if item:
                    declared.append(item.group(1))
                    continue
                if raw.strip() and not raw.startswith((" ", "\t", "-")):
                    break
        return {"path": path.name, "declared_capabilities": sorted(set(declared))}
    return {"path": None, "declared_capabilities": []}


def _extract_secret_ref(line: str) -> list[str]:
    names: set[str] = set()
    patterns = (
        r"os\.getenv\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"os\.environ(?:\.get)?\s*\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]",
        r"os\.environ\.get\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
        r"process\.env\.([A-Za-z_][A-Za-z0-9_]*)",
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
    )
    for pattern in patterns:
        names.update(re.findall(pattern, line))
    return sorted(name for name in names if SECRET_NAME_RE.search(name))


def snapshot(root: str | Path) -> Snapshot:
    base = Path(root).resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Skill path must be a directory: {base}")

    files: dict[str, str] = {}
    capability_evidence: dict[str, list[dict[str, object]]] = {key: [] for key in CAPABILITY_PATTERNS}
    domain_evidence: dict[str, list[dict[str, object]]] = {}
    secret_refs: dict[str, list[dict[str, object]]] = {}

    for path in _iter_text_files(base):
        rel = path.relative_to(base).as_posix()
        text = _read_text(path)
        files[rel] = _sha256(text)

        for line_no, line in enumerate(text.splitlines(), start=1):
            for capability, patterns in CAPABILITY_PATTERNS.items():
                if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns):
                    capability_evidence[capability].append(_evidence(rel, line_no, line))

            for match in re.finditer(r"https?://([^/\s)'\"<>]+)", line, flags=re.IGNORECASE):
                domain = match.group(1).lower().rstrip(".,;:")
                domain_evidence.setdefault(domain, []).append(_evidence(rel, line_no, line))

            for secret_name in _extract_secret_ref(line):
                secret_refs.setdefault(secret_name, []).append(_evidence(rel, line_no, line))

    manifest = _load_manifest(base)
    observed_caps = {key for key, value in capability_evidence.items() if value}
    declared_caps = set(manifest.get("declared_capabilities", []))
    manifest = {
        **manifest,
        "observed_capabilities": sorted(observed_caps),
        "undeclared_observed": sorted(observed_caps - declared_caps) if manifest.get("path") else [],
        "declared_not_observed": sorted(declared_caps - observed_caps) if manifest.get("path") else [],
    }

    return Snapshot(
        root=str(base),
        files=files,
        capabilities={key: value for key, value in capability_evidence.items() if value},
        domains={key: value for key, value in sorted(domain_evidence.items())},
        trigger_text=_extract_trigger_text(base / "SKILL.md"),
        dependencies=_extract_dependencies(base),
        secret_refs={key: value for key, value in sorted(secret_refs.items())},
        manifest=manifest,
    )


def _risk_level(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 3:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def compare(before: str | Path, after: str | Path) -> dict:
    old = snapshot(before)
    new = snapshot(after)

    old_files = set(old.files)
    new_files = set(new.files)
    added_files = sorted(new_files - old_files)
    removed_files = sorted(old_files - new_files)
    changed_files = sorted(path for path in old_files & new_files if old.files[path] != new.files[path])

    old_caps = set(old.capabilities)
    new_caps = set(new.capabilities)
    added_caps = sorted(new_caps - old_caps)
    removed_caps = sorted(old_caps - new_caps)

    old_domains = set(old.domains)
    new_domains = set(new.domains)
    added_domains = sorted(new_domains - old_domains)
    removed_domains = sorted(old_domains - new_domains)

    old_deps = set(old.dependencies)
    new_deps = set(new.dependencies)
    added_deps = sorted(new_deps - old_deps)
    removed_deps = sorted(old_deps - new_deps)

    old_secrets = set(old.secret_refs)
    new_secrets = set(new.secret_refs)
    added_secrets = sorted(new_secrets - old_secrets)
    removed_secrets = sorted(old_secrets - new_secrets)

    trigger = _trigger_diff(old.trigger_text, new.trigger_text)

    score = sum(RISK_WEIGHTS.get(cap, 1) for cap in added_caps)
    score += min(len(added_domains), 3)
    score += min(len(added_deps), 3)
    score += min(len(added_secrets) * 2, 4)
    score += {"none": 0, "low": 1, "medium": 2, "high": 4, "unknown": 0}[trigger["estimated_expansion"]]

    undeclared = list(new.manifest.get("undeclared_observed", []))
    if undeclared:
        score += min(len(undeclared), 3)

    explanations: list[str] = []
    if added_caps:
        explanations.append(f"New capabilities detected: {', '.join(added_caps)}.")
    if added_domains:
        explanations.append(f"New network domains detected: {', '.join(added_domains)}.")
    if added_deps:
        explanations.append(f"New dependencies detected: {', '.join(added_deps)}.")
    if added_secrets:
        explanations.append(f"New secret-like environment references detected: {', '.join(added_secrets)}.")
    if trigger["estimated_expansion"] in {"medium", "high"}:
        explanations.append(
            f"Skill trigger scope appears to have expanded ({trigger['estimated_expansion']})."
        )
    if undeclared:
        explanations.append(f"Observed capabilities are not declared by the manifest: {', '.join(undeclared)}.")
    if not explanations:
        explanations.append("No new high-signal trust boundary changes detected.")

    return {
        "schema_version": "0.2",
        "before": old.root,
        "after": new.root,
        "files": {"added": added_files, "removed": removed_files, "changed": changed_files},
        "capabilities": {
            "added": added_caps,
            "removed": removed_caps,
            "evidence_after": new.capabilities,
        },
        "capability_manifest": new.manifest,
        "network_domains": {
            "added": added_domains,
            "removed": removed_domains,
            "evidence_after": new.domains,
        },
        "dependencies": {"added": added_deps, "removed": removed_deps, "after": new.dependencies},
        "secret_access": {
            "added": added_secrets,
            "removed": removed_secrets,
            "evidence_after": new.secret_refs,
        },
        "trigger_scope": trigger,
        "risk": {
            "level": _risk_level(score),
            "score": score,
            "explanations": explanations,
        },
    }


def render_text(report: dict) -> str:
    trigger = report["trigger_scope"]
    manifest = report["capability_manifest"]
    lines = [
        "TrustForge SkillDiff",
        "====================",
        f"Risk: {report['risk']['level'].upper()} (score={report['risk']['score']})",
        "",
        "Why:",
    ]
    lines.extend(f"  - {item}" for item in report["risk"]["explanations"])
    lines.extend(
        [
            "",
            f"Added capabilities: {', '.join(report['capabilities']['added']) if report['capabilities']['added'] else 'none'}",
            f"Removed capabilities: {', '.join(report['capabilities']['removed']) if report['capabilities']['removed'] else 'none'}",
            f"Added domains: {', '.join(report['network_domains']['added']) if report['network_domains']['added'] else 'none'}",
            f"Added dependencies: {', '.join(report['dependencies']['added']) if report['dependencies']['added'] else 'none'}",
            f"New secret refs: {', '.join(report['secret_access']['added']) if report['secret_access']['added'] else 'none'}",
            "",
            "Trigger scope:",
            f"  Estimated expansion: {str(trigger['estimated_expansion']).upper()}",
            f"  New terms: {', '.join(trigger['added_terms']) if trigger['added_terms'] else 'none'}",
        ]
    )
    if trigger["term_ratio"] is not None:
        lines.append(f"  Term ratio: {trigger['term_ratio']}x")

    if manifest.get("path"):
        lines.extend(
            [
                "",
                f"Capability manifest: {manifest['path']}",
                f"  Undeclared observed: {', '.join(manifest['undeclared_observed']) if manifest['undeclared_observed'] else 'none'}",
                f"  Declared not observed: {', '.join(manifest['declared_not_observed']) if manifest['declared_not_observed'] else 'none'}",
            ]
        )

    lines.append("")
    for key in ("added", "removed", "changed"):
        values = report["files"][key]
        lines.append(f"Files {key}: {len(values)}")
        lines.extend(f"  - {value}" for value in values)

    if report["capabilities"]["added"]:
        lines.extend(["", "Evidence:"])
        for capability in report["capabilities"]["added"]:
            for evidence in report["capabilities"]["evidence_after"].get(capability, [])[:3]:
                lines.append(
                    f"  - {capability}: {evidence['path']}:{evidence['line']} — {evidence['excerpt']}"
                )

    return "\n".join(lines)


def dumps(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def to_sarif(report: dict) -> dict:
    results: list[dict[str, object]] = []

    severity_map = {
        "network": "warning",
        "subprocess": "error",
        "environment_read": "warning",
        "filesystem_read": "note",
        "filesystem_write": "warning",
        "dynamic_execution": "error",
        "credential_material": "error",
    }

    for capability in report["capabilities"]["added"]:
        for evidence in report["capabilities"]["evidence_after"].get(capability, [])[:10]:
            results.append(
                {
                    "ruleId": f"trustforge.capability.{capability}",
                    "level": severity_map.get(capability, "warning"),
                    "message": {"text": f"New capability detected: {capability}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": evidence["path"]},
                                "region": {"startLine": evidence["line"]},
                            }
                        }
                    ],
                }
            )

    for secret in report["secret_access"]["added"]:
        for evidence in report["secret_access"]["evidence_after"].get(secret, [])[:10]:
            results.append(
                {
                    "ruleId": "trustforge.secret-access",
                    "level": "error",
                    "message": {"text": f"New secret-like environment reference detected: {secret}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": evidence["path"]},
                                "region": {"startLine": evidence["line"]},
                            }
                        }
                    ],
                }
            )

    if report["trigger_scope"]["estimated_expansion"] in {"medium", "high"}:
        results.append(
            {
                "ruleId": "trustforge.trigger-scope-expansion",
                "level": "warning",
                "message": {
                    "text": (
                        "Skill trigger scope appears to have expanded. "
                        f"New terms: {', '.join(report['trigger_scope']['added_terms'])}"
                    )
                },
            }
        )

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "TrustForge SkillDiff",
                        "informationUri": "https://github.com/ptrgiang/trustforge-skills",
                        "version": "0.2.0",
                    }
                },
                "results": results,
            }
        ],
    }


def dumps_sarif(report: dict) -> str:
    return json.dumps(to_sarif(report), indent=2, sort_keys=True)
