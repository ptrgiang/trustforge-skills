from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SECRET_NAME_RE = re.compile(
    r"(?:secret|token|password|passwd|api[_-]?key|private[_-]?key|client[_-]?secret|credential)",
    re.IGNORECASE,
)

NETWORK_PREFIXES = (
    "requests.",
    "httpx.",
    "urllib.request.",
    "socket.",
    "aiohttp.",
)
SUBPROCESS_CALLS = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
    "os.popen",
}
READ_METHODS = {"read_text", "read_bytes", "read"}
WRITE_METHODS = {"write_text", "write_bytes", "write"}
FS_MUTATION_CALLS = {
    "shutil.copy",
    "shutil.copy2",
    "shutil.move",
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "os.mkdir",
    "os.makedirs",
}
DYNAMIC_CALLS = {"eval", "exec", "compile"}


@dataclass(frozen=True)
class Finding:
    capability: str
    path: str
    line: int
    excerpt: str
    symbol: str
    confidence: str = "high"
    detector: str = "python-ast-v1"

    @property
    def signature(self) -> str:
        return f"{self.capability}:{self.symbol}"

    def to_dict(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "path": self.path,
            "line": self.line,
            "excerpt": self.excerpt,
            "symbol": self.symbol,
            "signature": self.signature,
            "confidence": self.confidence,
            "detector": self.detector,
        }


@dataclass(frozen=True)
class ScanResult:
    findings: list[Finding]
    parse_errors: list[dict[str, object]]
    files_scanned: int

    def to_dict(self) -> dict[str, object]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "parse_errors": self.parse_errors,
            "files_scanned": self.files_scanned,
        }


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.is_file():
            yield path


def _line_excerpt(lines: list[str], line: int) -> str:
    if line <= 0 or line > len(lines):
        return ""
    text = lines[line - 1].strip()
    return text if len(text) <= 180 else text[:177] + "..."


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, rel: str, lines: list[str]) -> None:
        self.rel = rel
        self.lines = lines
        self.aliases: dict[str, str] = {}
        self.findings: list[Finding] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self.aliases[local] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            self.aliases[local] = f"{module}.{alias.name}" if module else alias.name
        self.generic_visit(node)

    def _resolve(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._resolve(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    def _add(self, capability: str, node: ast.AST, symbol: str, confidence: str = "high") -> None:
        line = int(getattr(node, "lineno", 0) or 0)
        finding = Finding(
            capability=capability,
            path=self.rel,
            line=line,
            excerpt=_line_excerpt(self.lines, line),
            symbol=symbol,
            confidence=confidence,
        )
        if finding.signature not in {item.signature for item in self.findings}:
            self.findings.append(finding)

    def _classify_open(self, node: ast.Call) -> None:
        mode: str | None = None
        if len(node.args) >= 2:
            mode = _literal_string(node.args[1])
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode = _literal_string(keyword.value)
        mode = mode or "r"
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            self._add("filesystem_write", node, f"open(mode={mode})")
            if "+" in mode:
                self._add("filesystem_read", node, f"open(mode={mode})")
        else:
            self._add("filesystem_read", node, f"open(mode={mode})")

    def _classify_environment(self, node: ast.Call, symbol: str) -> None:
        if symbol not in {"os.getenv", "os.environ.get"}:
            return
        self._add("environment_read", node, symbol)
        if node.args:
            env_name = _literal_string(node.args[0])
            if env_name and SECRET_NAME_RE.search(env_name):
                self._add("credential_material", node, f"env:{env_name}")

    def visit_Subscript(self, node: ast.Subscript) -> None:
        symbol = self._resolve(node.value)
        if symbol == "os.environ":
            self._add("environment_read", node, "os.environ[]")
            env_name = _literal_string(node.slice)
            if env_name and SECRET_NAME_RE.search(env_name):
                self._add("credential_material", node, f"env:{env_name}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        symbol = self._resolve(node.func)

        if symbol == "open":
            self._classify_open(node)
        if symbol.startswith(NETWORK_PREFIXES):
            self._add("network", node, symbol)
        if symbol in SUBPROCESS_CALLS:
            self._add("subprocess", node, symbol)
        self._classify_environment(node, symbol)

        tail = symbol.rsplit(".", 1)[-1] if symbol else ""
        if tail in READ_METHODS and symbol != "os.environ.get":
            self._add("filesystem_read", node, symbol, confidence="medium")
        if tail in WRITE_METHODS:
            self._add("filesystem_write", node, symbol, confidence="medium")
        if symbol in FS_MUTATION_CALLS:
            self._add("filesystem_write", node, symbol)
        if symbol in DYNAMIC_CALLS:
            self._add("dynamic_execution", node, symbol)

        self.generic_visit(node)


def scan_python_tree(root: str | Path) -> ScanResult:
    base = Path(root).resolve()
    findings: list[Finding] = []
    parse_errors: list[dict[str, object]] = []
    files_scanned = 0

    for path in _iter_python_files(base):
        files_scanned += 1
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            parse_errors.append(
                {
                    "path": rel,
                    "line": exc.lineno or 0,
                    "message": exc.msg,
                }
            )
            continue

        visitor = _PythonVisitor(rel, lines)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    findings.sort(key=lambda item: (item.path, item.line, item.capability, item.symbol))
    return ScanResult(findings=findings, parse_errors=parse_errors, files_scanned=files_scanned)


def compare_python_ast(before: str | Path, after: str | Path) -> dict[str, object]:
    old = scan_python_tree(before)
    new = scan_python_tree(after)

    old_signatures = {finding.signature for finding in old.findings}
    new_signatures = {finding.signature for finding in new.findings}
    added_findings = [finding for finding in new.findings if finding.signature not in old_signatures]

    before_capabilities = {finding.capability for finding in old.findings}
    after_capabilities = {finding.capability for finding in new.findings}

    return {
        "detector": "python-ast-v1",
        "files_scanned_before": old.files_scanned,
        "files_scanned_after": new.files_scanned,
        "parse_errors_before": old.parse_errors,
        "parse_errors_after": new.parse_errors,
        "new_capabilities": sorted(after_capabilities - before_capabilities),
        "removed_capabilities": sorted(before_capabilities - after_capabilities),
        "added_signatures": sorted(new_signatures - old_signatures),
        "removed_signatures": sorted(old_signatures - new_signatures),
        "added_findings": [finding.to_dict() for finding in added_findings],
        "findings_after": [finding.to_dict() for finding in new.findings],
        "note": "Python AST analysis is static and does not execute candidate code.",
    }
