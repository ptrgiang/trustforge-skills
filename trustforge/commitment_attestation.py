from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class AttestationError(ValueError):
    """Raised when an evidence attestation is malformed or cannot be verified."""


ATTESTATION_SCHEMA_VERSION = "0.1"
ATTESTATION_ALGORITHM = "Ed25519"


def _canonical_json(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AttestationError(f"value is not canonical-JSON serializable: {exc}") from exc
    return text.encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _parse_time(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AttestationError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AttestationError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise AttestationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _normalize_time(value: str, field: str) -> str:
    return _parse_time(value, field).isoformat().replace("+00:00", "Z")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise AttestationError("signature must be a non-empty base64url string")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise AttestationError("signature must be valid base64url") from exc


def load_private_key_pem(data: bytes) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except (TypeError, ValueError) as exc:
        raise AttestationError("invalid unencrypted PEM private key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise AttestationError("private key must be Ed25519")
    return key


def load_public_key_pem(data: bytes) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(data)
    except (TypeError, ValueError) as exc:
        raise AttestationError("invalid PEM public key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise AttestationError("public key must be Ed25519")
    return key


def public_key_pem(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def private_key_pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _payload(
    *,
    observation_key: str,
    value: Any,
    provenance: Mapping[str, Any] | None,
    issuer: str,
    key_id: str,
    issued_at: str,
    expires_at: str | None,
) -> dict[str, Any]:
    if not isinstance(observation_key, str) or not observation_key:
        raise AttestationError("observation_key must be a non-empty string")
    if not isinstance(issuer, str) or not issuer:
        raise AttestationError("issuer must be a non-empty string")
    if not isinstance(key_id, str) or not key_id:
        raise AttestationError("key_id must be a non-empty string")

    normalized_issued_at = _normalize_time(issued_at, "issued_at")
    normalized_expires_at = None
    if expires_at is not None:
        normalized_expires_at = _normalize_time(expires_at, "expires_at")
        if _parse_time(normalized_expires_at, "expires_at") <= _parse_time(normalized_issued_at, "issued_at"):
            raise AttestationError("expires_at must be later than issued_at")

    return {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "algorithm": ATTESTATION_ALGORITHM,
        "issuer": issuer,
        "key_id": key_id,
        "observation_key": observation_key,
        "value_sha256": _sha256_json(value),
        "provenance_sha256": _sha256_json(dict(provenance or {})),
        "issued_at": normalized_issued_at,
        "expires_at": normalized_expires_at,
    }


def sign_observation(
    *,
    observation_key: str,
    value: Any,
    provenance: Mapping[str, Any] | None,
    private_key: Ed25519PrivateKey,
    issuer: str,
    key_id: str,
    issued_at: str,
    expires_at: str | None = None,
) -> dict[str, Any]:
    payload = _payload(
        observation_key=observation_key,
        value=value,
        provenance=provenance,
        issuer=issuer,
        key_id=key_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = private_key.sign(_canonical_json(payload))
    return {**payload, "signature": _b64url_encode(signature)}


def verify_observation_attestation(
    *,
    observation_key: str,
    value: Any,
    provenance: Mapping[str, Any] | None,
    attestation: Mapping[str, Any],
    trusted_keys: Mapping[tuple[str, str], Ed25519PublicKey],
    as_of: str | None = None,
) -> dict[str, Any]:
    if not isinstance(attestation, Mapping):
        raise AttestationError("attestation must be an object")

    required_fields = {
        "schema_version",
        "algorithm",
        "issuer",
        "key_id",
        "observation_key",
        "value_sha256",
        "provenance_sha256",
        "issued_at",
        "expires_at",
        "signature",
    }
    unknown = sorted(set(attestation) - required_fields)
    missing = sorted(required_fields - set(attestation))
    if missing:
        raise AttestationError(f"attestation missing fields: {', '.join(missing)}")
    if unknown:
        raise AttestationError(f"attestation has unknown fields: {', '.join(unknown)}")
    if attestation["schema_version"] != ATTESTATION_SCHEMA_VERSION:
        raise AttestationError(f"attestation.schema_version must be {ATTESTATION_SCHEMA_VERSION}")
    if attestation["algorithm"] != ATTESTATION_ALGORITHM:
        raise AttestationError(f"attestation.algorithm must be {ATTESTATION_ALGORITHM}")

    issuer = attestation["issuer"]
    key_id = attestation["key_id"]
    if not isinstance(issuer, str) or not issuer or not isinstance(key_id, str) or not key_id:
        raise AttestationError("attestation issuer/key_id must be non-empty strings")

    expected_payload = _payload(
        observation_key=observation_key,
        value=value,
        provenance=provenance,
        issuer=issuer,
        key_id=key_id,
        issued_at=attestation["issued_at"],
        expires_at=attestation["expires_at"],
    )
    signed_payload = {key: attestation[key] for key in expected_payload}
    if signed_payload != expected_payload:
        raise AttestationError("attestation payload does not match observation")

    public_key = trusted_keys.get((issuer, key_id))
    if public_key is None:
        raise AttestationError(f"untrusted attestation key: issuer={issuer!r} key_id={key_id!r}")

    signature = _b64url_decode(attestation["signature"])
    try:
        public_key.verify(signature, _canonical_json(signed_payload))
    except InvalidSignature as exc:
        raise AttestationError("invalid attestation signature") from exc

    issued_at = _parse_time(attestation["issued_at"], "issued_at")
    evaluation_time = datetime.now(timezone.utc) if as_of is None else _parse_time(as_of, "as_of")
    if issued_at > evaluation_time:
        raise AttestationError("attestation is future-dated")
    expires_at = attestation["expires_at"]
    if expires_at is not None and evaluation_time >= _parse_time(expires_at, "expires_at"):
        raise AttestationError("attestation is expired")

    return {
        "verified": True,
        "issuer": issuer,
        "key_id": key_id,
        "algorithm": ATTESTATION_ALGORITHM,
        "issued_at": attestation["issued_at"],
        "expires_at": expires_at,
    }
