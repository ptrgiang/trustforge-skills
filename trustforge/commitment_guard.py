from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .commitment_attestation import AttestationError, verify_observation_attestation


class CommitmentGuardError(ValueError):
    """Raised when a commitment contract or evidence bundle is invalid."""


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommitmentGuardError(str(exc)) from exc
    if not isinstance(data, dict):
        raise CommitmentGuardError("document must be a JSON object")
    return data


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommitmentGuardError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CommitmentGuardError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _resolve_as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return _parse_time(value, "as_of")


def _get_nested(mapping: dict[str, Any], dotted_key: str) -> tuple[bool, Any]:
    value: Any = mapping
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def _check(actual: Any, rule: dict[str, Any]) -> tuple[str, str]:
    operators = [name for name in ("equals", "gte", "lte", "truthy", "contains") if name in rule]
    if len(operators) != 1:
        return "UNKNOWN", "evidence rule must contain exactly one supported check operator"

    operator = operators[0]
    if operator == "equals":
        expected = rule["equals"]
        return ("PASS", f"equals {expected!r}") if actual == expected else ("FAIL", f"expected {expected!r}, got {actual!r}")
    if operator == "gte":
        expected = rule["gte"]
        try:
            ok = actual >= expected
        except TypeError:
            ok = False
        return ("PASS", f">= {expected!r}") if ok else ("FAIL", f"expected >= {expected!r}, got {actual!r}")
    if operator == "lte":
        expected = rule["lte"]
        try:
            ok = actual <= expected
        except TypeError:
            ok = False
        return ("PASS", f"<= {expected!r}") if ok else ("FAIL", f"expected <= {expected!r}, got {actual!r}")
    if operator == "truthy":
        if rule["truthy"] is not True:
            return "UNKNOWN", "truthy operator currently requires true"
        return ("PASS", "truthy") if bool(actual) else ("FAIL", f"expected truthy, got {actual!r}")

    expected = rule["contains"]
    try:
        ok = expected in actual
    except TypeError:
        ok = False
    return ("PASS", f"contains {expected!r}") if ok else ("FAIL", f"expected value containing {expected!r}, got {actual!r}")


def _validate_string_list(cid: str, rule: dict[str, Any], field: str) -> None:
    if field not in rule:
        return
    values = rule[field]
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
        raise CommitmentGuardError(f"commitment {cid}.evidence.{field} must be a non-empty list of strings")


def _validate_evidence_rule(cid: str, rule: Any) -> None:
    if not isinstance(rule, dict) or not isinstance(rule.get("key"), str) or not rule["key"]:
        return
    if "max_age_seconds" in rule:
        value = rule["max_age_seconds"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise CommitmentGuardError(f"commitment {cid}.evidence.max_age_seconds must be a non-negative number")
    for field in ("allowed_source_kinds", "allowed_attestation_issuers", "allowed_attestation_key_ids"):
        _validate_string_list(cid, rule, field)
    if "require_attestation" in rule and not isinstance(rule["require_attestation"], bool):
        raise CommitmentGuardError(f"commitment {cid}.evidence.require_attestation must be boolean")
    if ("allowed_attestation_issuers" in rule or "allowed_attestation_key_ids" in rule) and rule.get("require_attestation") is not True:
        raise CommitmentGuardError(
            f"commitment {cid}.evidence.require_attestation must be true when attestation issuer/key policy is configured"
        )


def _validate_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    schema_version = str(contract.get("schema_version", "0.1"))
    if schema_version not in {"0.1", "0.2"}:
        raise CommitmentGuardError("contract.schema_version must be 0.1 or 0.2")

    commitments = contract.get("commitments")
    if not isinstance(commitments, list) or not commitments:
        raise CommitmentGuardError("contract.commitments must be a non-empty list")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(commitments):
        if not isinstance(raw, dict):
            raise CommitmentGuardError(f"commitment at index {index} must be an object")
        cid = str(raw.get("id", "")).strip()
        if not cid:
            raise CommitmentGuardError(f"commitment at index {index} must have a non-empty id")
        if cid in seen:
            raise CommitmentGuardError(f"duplicate commitment id: {cid}")
        seen.add(cid)
        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise CommitmentGuardError(f"commitment {cid}.required must be boolean")
        _validate_evidence_rule(cid, raw.get("evidence"))
        normalized.append(raw)
    return normalized


def _validate_evidence_bundle(evidence: dict[str, Any]) -> None:
    if "observations" not in evidence:
        return
    if str(evidence.get("schema_version", "")) != "0.2":
        raise CommitmentGuardError("evidence.schema_version must be 0.2 when observations are used")
    observations = evidence["observations"]
    if not isinstance(observations, dict):
        raise CommitmentGuardError("evidence.observations must be an object")


def _observation(
    evidence: dict[str, Any],
    key: str,
) -> tuple[bool, Any, dict[str, Any] | None, dict[str, Any] | None]:
    observations = evidence.get("observations")
    if isinstance(observations, dict):
        item = observations.get(key)
        if item is None:
            return False, None, None, None
        if not isinstance(item, dict) or "value" not in item:
            raise CommitmentGuardError(f"evidence observation {key!r} must be an object with value")
        provenance: dict[str, Any] = {}
        if "source" in item:
            if not isinstance(item["source"], dict):
                raise CommitmentGuardError(f"evidence observation {key!r}.source must be an object")
            provenance["source"] = item["source"]
        if "observed_at" in item:
            if not isinstance(item["observed_at"], str) or not item["observed_at"]:
                raise CommitmentGuardError(f"evidence observation {key!r}.observed_at must be a non-empty string")
            _parse_time(item["observed_at"], f"evidence observation {key!r}.observed_at")
            provenance["observed_at"] = item["observed_at"]
        attestation = item.get("attestation")
        if attestation is not None and not isinstance(attestation, dict):
            raise CommitmentGuardError(f"evidence observation {key!r}.attestation must be an object")
        return True, item["value"], provenance or None, attestation

    found, actual = _get_nested(evidence, key)
    return found, actual, None, None


def _check_attestation_policy(
    rule: dict[str, Any],
    *,
    key: str,
    actual: Any,
    provenance: dict[str, Any] | None,
    attestation: dict[str, Any] | None,
    as_of: datetime,
    trusted_attestation_keys: Mapping[tuple[str, str], Ed25519PublicKey] | None,
) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
    if rule.get("require_attestation") is not True:
        return None, None
    if attestation is None:
        return ("UNKNOWN", "evidence attestation required by policy"), None
    if not trusted_attestation_keys:
        return ("UNKNOWN", "trusted attestation keys required by policy"), None

    as_of_text = as_of.isoformat().replace("+00:00", "Z")
    try:
        verification = verify_observation_attestation(
            observation_key=key,
            value=actual,
            provenance=provenance,
            attestation=attestation,
            trusted_keys=trusted_attestation_keys,
            as_of=as_of_text,
        )
    except AttestationError as exc:
        return ("UNKNOWN", f"attestation verification failed: {exc}"), None

    allowed_issuers = rule.get("allowed_attestation_issuers")
    if allowed_issuers is not None and verification["issuer"] not in allowed_issuers:
        return ("UNKNOWN", f"attestation issuer {verification['issuer']!r} is not allowed"), None
    allowed_key_ids = rule.get("allowed_attestation_key_ids")
    if allowed_key_ids is not None and verification["key_id"] not in allowed_key_ids:
        return ("UNKNOWN", f"attestation key_id {verification['key_id']!r} is not allowed"), None
    return None, verification


def _check_evidence_policy(
    rule: dict[str, Any],
    provenance: dict[str, Any] | None,
    as_of: datetime,
) -> tuple[str, str] | None:
    allowed_source_kinds = rule.get("allowed_source_kinds")
    if allowed_source_kinds is not None:
        source = provenance.get("source") if provenance else None
        source_kind = source.get("kind") if isinstance(source, dict) else None
        if not isinstance(source_kind, str) or not source_kind:
            return "UNKNOWN", "evidence source kind required by policy"
        if source_kind not in allowed_source_kinds:
            return "UNKNOWN", f"evidence source kind {source_kind!r} is not allowed"

    max_age_seconds = rule.get("max_age_seconds")
    if max_age_seconds is not None:
        observed_at = provenance.get("observed_at") if provenance else None
        if not isinstance(observed_at, str):
            return "UNKNOWN", "observed_at required by freshness policy"
        observed = _parse_time(observed_at, "evidence observed_at")
        age_seconds = (as_of - observed).total_seconds()
        if age_seconds < 0:
            return "UNKNOWN", "evidence observation is future-dated"
        if age_seconds > float(max_age_seconds):
            return "UNKNOWN", f"evidence is stale: age {age_seconds:.0f}s exceeds {float(max_age_seconds):.0f}s"
    return None


def _waiver_result(
    cid: str,
    description: str,
    required: bool,
    waiver: Any,
    as_of: datetime,
) -> dict[str, Any] | None:
    if not waiver:
        return None
    if isinstance(waiver, str):
        return {
            "id": cid,
            "description": description,
            "required": required,
            "status": "WAIVED",
            "detail": waiver,
            "waiver": {"reason": waiver, "legacy": True},
        }
    if not isinstance(waiver, dict):
        raise CommitmentGuardError(f"commitment {cid}.waiver must be a string or object")
    reason = waiver.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise CommitmentGuardError(f"commitment {cid}.waiver.reason must be a non-empty string")
    allowed = {"reason", "approved_by", "ticket", "expires_at"}
    unknown = sorted(set(waiver) - allowed)
    if unknown:
        raise CommitmentGuardError(f"commitment {cid}.waiver has unknown fields: {', '.join(unknown)}")
    result_waiver = {"reason": reason}
    for key in ("approved_by", "ticket", "expires_at"):
        if key in waiver:
            if not isinstance(waiver[key], str) or not waiver[key]:
                raise CommitmentGuardError(f"commitment {cid}.waiver.{key} must be a non-empty string")
            result_waiver[key] = waiver[key]
    if "expires_at" in result_waiver:
        expiry = _parse_time(result_waiver["expires_at"], f"commitment {cid}.waiver.expires_at")
        if as_of >= expiry:
            return {
                "id": cid,
                "description": description,
                "required": required,
                "status": "UNKNOWN",
                "detail": "waiver is expired",
                "waiver": result_waiver,
            }
    return {
        "id": cid,
        "description": description,
        "required": required,
        "status": "WAIVED",
        "detail": reason,
        "waiver": result_waiver,
    }


def verify(
    contract: dict[str, Any],
    evidence: dict[str, Any],
    *,
    as_of: str | None = None,
    trusted_attestation_keys: Mapping[tuple[str, str], Ed25519PublicKey] | None = None,
) -> dict[str, Any]:
    commitments = _validate_contract(contract)
    _validate_evidence_bundle(evidence)
    evaluation_time = _resolve_as_of(as_of)
    results: list[dict[str, Any]] = []

    for item in commitments:
        cid = str(item["id"])
        description = str(item.get("description", ""))
        required = item.get("required", True)

        waived = _waiver_result(cid, description, required, item.get("waiver"), evaluation_time)
        if waived is not None:
            results.append(waived)
            continue

        rule = item.get("evidence")
        if not isinstance(rule, dict) or not isinstance(rule.get("key"), str) or not rule["key"]:
            results.append({
                "id": cid,
                "description": description,
                "required": required,
                "status": "UNKNOWN",
                "detail": "missing evidence rule",
            })
            continue

        key = rule["key"]
        found, actual, provenance, attestation = _observation(evidence, key)
        if not found:
            results.append({
                "id": cid,
                "description": description,
                "required": required,
                "status": "UNKNOWN",
                "detail": f"evidence key not found: {key}",
                "evidence_key": key,
            })
            continue

        attestation_result, attestation_verification = _check_attestation_policy(
            rule,
            key=key,
            actual=actual,
            provenance=provenance,
            attestation=attestation,
            as_of=evaluation_time,
            trusted_attestation_keys=trusted_attestation_keys,
        )
        if attestation_result is not None:
            status, detail = attestation_result
        else:
            policy_result = _check_evidence_policy(rule, provenance, evaluation_time)
            if policy_result is not None:
                status, detail = policy_result
            else:
                status, detail = _check(actual, rule)

        result: dict[str, Any] = {
            "id": cid,
            "description": description,
            "required": required,
            "status": status,
            "detail": detail,
            "evidence_key": key,
            "actual": actual,
        }
        if provenance is not None:
            result["provenance"] = provenance
        if attestation_verification is not None:
            result["attestation"] = attestation_verification
        results.append(result)

    required_blockers = [
        result for result in results
        if result["required"] and result["status"] in {"FAIL", "UNKNOWN"}
    ]
    any_incomplete = any(result["status"] in {"FAIL", "UNKNOWN"} for result in results)
    if required_blockers:
        completion_state = "not_verified"
    elif any_incomplete:
        completion_state = "partial"
    else:
        completion_state = "verified_complete"

    return {
        "schema_version": "0.2",
        "as_of": evaluation_time.isoformat().replace("+00:00", "Z"),
        "verified_complete": completion_state == "verified_complete",
        "required_satisfied": not required_blockers,
        "completion_state": completion_state,
        "summary": {
            "pass": sum(r["status"] == "PASS" for r in results),
            "fail": sum(r["status"] == "FAIL" for r in results),
            "unknown": sum(r["status"] == "UNKNOWN" for r in results),
            "waived": sum(r["status"] == "WAIVED" for r in results),
            "required_blockers": len(required_blockers),
        },
        "commitments": results,
    }


def verify_files(
    contract_path: str | Path,
    evidence_path: str | Path,
    *,
    as_of: str | None = None,
    trusted_attestation_keys: Mapping[tuple[str, str], Ed25519PublicKey] | None = None,
) -> dict[str, Any]:
    return verify(
        _load_json(contract_path),
        _load_json(evidence_path),
        as_of=as_of,
        trusted_attestation_keys=trusted_attestation_keys,
    )


def render_text(report: dict[str, Any]) -> str:
    lines = ["TrustForge CommitmentGuard", "==========================", "", f"As of: {report['as_of']}", ""]
    for item in report["commitments"]:
        scope = "required" if item.get("required", True) else "optional"
        lines.append(f"{item['id']} {item['status']} ({scope}): {item['description']}")
        lines.append(f"  {item['detail']}")
        provenance = item.get("provenance")
        if provenance:
            source = provenance.get("source")
            observed_at = provenance.get("observed_at")
            if source:
                lines.append(f"  source: {json.dumps(source, sort_keys=True)}")
            if observed_at:
                lines.append(f"  observed_at: {observed_at}")
        attestation = item.get("attestation")
        if attestation:
            lines.append(
                f"  attestation: verified issuer={attestation['issuer']!r} key_id={attestation['key_id']!r}"
            )
    lines.extend(["", f"Result: {report['completion_state'].upper()}"])
    return "\n".join(lines)
