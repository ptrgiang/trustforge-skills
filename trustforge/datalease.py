from __future__ import annotations

import fnmatch
import ipaddress
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - package dependency should normally provide it.
    yaml = None


class DataLeaseError(ValueError):
    """Raised when a DataLease policy or payload cannot be processed."""


_REMOVE = object()

SECRET_NAME_RE = re.compile(
    r"(?:^|[._-])(?:secret|token|password|passwd|api[_-]?key|private[_-]?key|client[_-]?secret|credential)(?:$|[._-])",
    re.IGNORECASE,
)
EMAIL_NAME_RE = re.compile(r"(?:^|[._-])e?mail(?:$|[._-])", re.IGNORECASE)
PHONE_NAME_RE = re.compile(r"(?:^|[._-])(?:phone|mobile|telephone|tel)(?:$|[._-])", re.IGNORECASE)
ADDRESS_NAME_RE = re.compile(
    r"(?:^|[._-])(?:address|street|city|state|province|postal|postcode|zip)(?:$|[._-])",
    re.IGNORECASE,
)
NAME_NAME_RE = re.compile(
    r"(?:^|[._-])(?:full[_-]?name|first[_-]?name|last[_-]?name|given[_-]?name|family[_-]?name)(?:$|[._-])",
    re.IGNORECASE,
)
DOB_NAME_RE = re.compile(r"(?:^|[._-])(?:dob|date[_-]?of[_-]?birth|birth[_-]?date)(?:$|[._-])", re.IGNORECASE)
GOV_ID_NAME_RE = re.compile(
    r"(?:^|[._-])(?:ssn|social[_-]?security|national[_-]?id|passport|tax[_-]?id)(?:$|[._-])",
    re.IGNORECASE,
)
PAYMENT_NAME_RE = re.compile(
    r"(?:^|[._-])(?:card[_-]?number|credit[_-]?card|cvv|cvc|iban|bank[_-]?account)(?:$|[._-])",
    re.IGNORECASE,
)
EMAIL_VALUE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_VALUE_RE = re.compile(r"^\+?[0-9][0-9().\-\s]{6,}[0-9]$")


def _normalize_purpose(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def load_policy(path: str | Path) -> dict[str, Any]:
    policy_path = Path(path)
    text = policy_path.read_text(encoding="utf-8")

    if policy_path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DataLeaseError(f"Invalid JSON policy: {exc}") from exc
    elif policy_path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise DataLeaseError("YAML policy support requires PyYAML.")
        try:
            data = yaml.safe_load(text)
        except Exception as exc:
            raise DataLeaseError(f"Invalid YAML policy: {exc}") from exc
    else:
        raise DataLeaseError("Policy must be .json, .yaml, or .yml")

    if not isinstance(data, dict):
        raise DataLeaseError("Policy root must be an object.")
    validate_policy(data)
    return data


def validate_policy(policy: dict[str, Any]) -> None:
    version = str(policy.get("version", ""))
    if version not in {"0.1", "1"}:
        raise DataLeaseError("Policy version must be '0.1'.")

    purposes = _policy_purposes(policy)
    if not purposes:
        raise DataLeaseError("Policy must declare 'purpose' or non-empty 'purposes'.")

    default_action = str(policy.get("default_action", "deny"))
    if default_action not in {"allow", "redact", "deny"}:
        raise DataLeaseError("default_action must be allow, redact, or deny.")

    hard_deny = policy.get("hard_deny_classifiers", ["secret"])
    if isinstance(hard_deny, str):
        hard_deny = [hard_deny]
    if not isinstance(hard_deny, list) or not all(isinstance(item, str) for item in hard_deny):
        raise DataLeaseError("hard_deny_classifiers must be a string or list of strings.")

    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        raise DataLeaseError("rules must be a list.")

    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise DataLeaseError(f"rules[{index}] must be an object.")
        rule_id = str(rule.get("id", f"rule-{index + 1}"))
        if rule_id in seen_ids:
            raise DataLeaseError(f"Duplicate rule id: {rule_id}")
        seen_ids.add(rule_id)

        action = str(rule.get("action", ""))
        if action not in {"allow", "redact", "deny"}:
            raise DataLeaseError(f"Rule {rule_id} has invalid action: {action!r}")

        paths = rule.get("paths", [])
        classifiers = rule.get("classifiers", [])
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(classifiers, str):
            classifiers = [classifiers]
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise DataLeaseError(f"Rule {rule_id} paths must be a string or list of strings.")
        if not isinstance(classifiers, list) or not all(isinstance(item, str) for item in classifiers):
            raise DataLeaseError(f"Rule {rule_id} classifiers must be a string or list of strings.")
        if not paths and not classifiers:
            raise DataLeaseError(f"Rule {rule_id} must declare paths and/or classifiers.")

        if action == "redact":
            strategy = str(rule.get("strategy", policy.get("redaction_strategy", "mask")))
            if strategy not in {"mask", "null", "last4", "email_domain"}:
                raise DataLeaseError(f"Rule {rule_id} has unsupported redaction strategy: {strategy}")


def _policy_purposes(policy: dict[str, Any]) -> list[str]:
    values: list[str] = []
    if isinstance(policy.get("purpose"), str):
        values.append(policy["purpose"])
    raw = policy.get("purposes", [])
    if isinstance(raw, str):
        values.append(raw)
    elif isinstance(raw, list):
        values.extend(item for item in raw if isinstance(item, str))
    return [value for value in values if value.strip()]


def classify_field(path: str, value: Any) -> list[str]:
    classifiers: set[str] = set()

    if SECRET_NAME_RE.search(path):
        classifiers.add("secret")
    if EMAIL_NAME_RE.search(path):
        classifiers.add("pii.email")
    if PHONE_NAME_RE.search(path):
        classifiers.add("pii.phone")
    if ADDRESS_NAME_RE.search(path):
        classifiers.add("pii.address")
    if NAME_NAME_RE.search(path):
        classifiers.add("pii.name")
    if DOB_NAME_RE.search(path):
        classifiers.add("pii.dob")
    if GOV_ID_NAME_RE.search(path):
        classifiers.add("pii.government_id")
    if PAYMENT_NAME_RE.search(path):
        classifiers.add("pii.payment")

    if isinstance(value, str):
        stripped = value.strip()
        if EMAIL_VALUE_RE.fullmatch(stripped):
            classifiers.add("pii.email")
        if PHONE_VALUE_RE.fullmatch(stripped):
            digits = re.sub(r"\D", "", stripped)
            if 8 <= len(digits) <= 15:
                classifiers.add("pii.phone")
        try:
            ipaddress.ip_address(stripped)
        except ValueError:
            pass
        else:
            classifiers.add("network.ip")

    return sorted(classifiers)


def _matches_path(pattern: str, path: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def _normalize_rule(rule: dict[str, Any], index: int) -> dict[str, Any]:
    paths = rule.get("paths", [])
    classifiers = rule.get("classifiers", [])
    if isinstance(paths, str):
        paths = [paths]
    if isinstance(classifiers, str):
        classifiers = [classifiers]
    return {
        "id": str(rule.get("id", f"rule-{index + 1}")),
        "paths": list(paths),
        "classifiers": list(classifiers),
        "action": str(rule["action"]),
        "strategy": rule.get("strategy"),
        "reason": str(rule.get("reason", "")),
    }


def _select_rule(policy: dict[str, Any], path: str, classifiers: list[str]) -> dict[str, Any] | None:
    classifier_set = set(classifiers)
    for index, raw_rule in enumerate(policy.get("rules", [])):
        rule = _normalize_rule(raw_rule, index)
        path_ok = not rule["paths"] or any(_matches_path(pattern, path) for pattern in rule["paths"])
        classifier_ok = not rule["classifiers"] or bool(classifier_set.intersection(rule["classifiers"]))
        if path_ok and classifier_ok:
            return rule
    return None


def _redact(value: Any, strategy: str) -> Any:
    if strategy == "null":
        return None
    if strategy == "last4":
        text = str(value)
        return f"***{text[-4:]}" if len(text) >= 4 else "[REDACTED]"
    if strategy == "email_domain":
        text = str(value)
        if "@" in text:
            _, domain = text.rsplit("@", 1)
            return f"***@{domain}"
        return "[REDACTED]"
    return "[REDACTED]"


def _leaf_decision(
    policy: dict[str, Any],
    path: str,
    value: Any,
    audit: list[dict[str, Any]],
) -> Any:
    classifiers = classify_field(path, value)

    hard_deny = policy.get("hard_deny_classifiers", ["secret"])
    if isinstance(hard_deny, str):
        hard_deny = [hard_deny]
    hard_match = sorted(set(classifiers).intersection(hard_deny))
    if hard_match:
        audit.append(
            {
                "path": path,
                "action": "deny",
                "classifiers": classifiers,
                "rule_id": f"hard-deny:{hard_match[0]}",
                "reason": "Matched a policy hard-deny classifier.",
            }
        )
        return _REMOVE

    rule = _select_rule(policy, path, classifiers)

    if rule is None:
        action = str(policy.get("default_action", "deny"))
        strategy = str(policy.get("redaction_strategy", "mask"))
        rule_id = "default"
        reason = "No policy rule matched; applied default_action."
    else:
        action = rule["action"]
        strategy = str(rule.get("strategy") or policy.get("redaction_strategy", "mask"))
        rule_id = rule["id"]
        reason = rule["reason"] or "Matched policy rule."

    entry = {
        "path": path,
        "action": action,
        "classifiers": classifiers,
        "rule_id": rule_id,
        "reason": reason,
    }
    if action == "redact":
        entry["strategy"] = strategy
    audit.append(entry)

    if action == "allow":
        return value
    if action == "redact":
        return _redact(value, strategy)
    return _REMOVE


def _project(
    value: Any,
    policy: dict[str, Any],
    path: str,
    audit: list[dict[str, Any]],
) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            projected = _project(child, policy, child_path, audit)
            if projected is not _REMOVE:
                output[key] = projected
        return output if output else _REMOVE

    if isinstance(value, list):
        output_list: list[Any] = []
        for index, child in enumerate(value):
            child_path = f"{path}.{index}" if path else str(index)
            projected = _project(child, policy, child_path, audit)
            if projected is not _REMOVE:
                output_list.append(projected)
        return output_list if output_list else _REMOVE

    return _leaf_decision(policy, path or "$", value, audit)


def _summary(audit: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "allowed": sum(1 for item in audit if item.get("action") == "allow"),
        "redacted": sum(1 for item in audit if item.get("action") == "redact"),
        "denied": sum(1 for item in audit if item.get("action") == "deny"),
    }


def apply_policy(policy: dict[str, Any], purpose: str, payload: Any) -> dict[str, Any]:
    validate_policy(policy)
    allowed_purposes = _policy_purposes(policy)
    normalized_allowed = {_normalize_purpose(item) for item in allowed_purposes}
    requested = _normalize_purpose(purpose)

    if requested not in normalized_allowed:
        audit = [
            {
                "path": "$",
                "action": "deny",
                "classifiers": [],
                "rule_id": "purpose-binding",
                "reason": "Requested purpose is not authorized by this policy.",
            }
        ]
        return {
            "schema_version": "0.1",
            "decision": "denied",
            "purpose": purpose,
            "authorized_purposes": allowed_purposes,
            "output": None,
            "audit": audit,
            "summary": _summary(audit),
        }

    audit: list[dict[str, Any]] = []
    output = _project(payload, policy, "", audit)
    if output is _REMOVE:
        output = None

    return {
        "schema_version": "0.1",
        "decision": "projected",
        "purpose": purpose,
        "authorized_purposes": allowed_purposes,
        "output": output,
        "audit": audit,
        "summary": _summary(audit),
    }


def apply_files(
    policy_path: str | Path,
    input_path: str | Path,
    purpose: str,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    try:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataLeaseError(f"Invalid JSON input payload: {exc}") from exc
    return apply_policy(policy, purpose, payload)


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
